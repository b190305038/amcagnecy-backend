from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .attendance_rules import LEAVE_QUOTA, evaluate as evaluate_shift, leave_eligible_from

from .models import (
    AccountHead,
    Area,
    Attendance,
    Brand,
    CashbackTxn,
    CompanySettings,
    DamageRecord,
    Dealer,
    Employee,
    EmployeePunishment,
    EmployeeReward,
    ExpenseHead,
    InvoiceLine,
    LedgerEntry,
    Offer,
    OfferAccrual,
    Payment,
    Payout,
    Product,
    ProductCategory,
    ProductSegment,
    PromotionHistory,
    Region,
    SalesOrder,
    Salesman,
    Shop,
    ShopCategory,
    StockEntry,
    ShopReview,
    Target,
    Territory,
    Unit,
    Visit,
)


def _parse_iso_date(value):
    """"2026-09-20" -> date(2026,9,20). None for blank/unparseable input —
    the Attendance.date field is a plain string, not a DateField."""
    from datetime import date as _date

    try:
        return _date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class ProductSerializer(serializers.ModelSerializer):
    total_pcs = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["total_pcs", "createdAt"]

    def get_total_pcs(self, obj):
        return obj.total_pcs


class TargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Target
        fields = "__all__"


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = "__all__"


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["sku", "name", "qty", "price"]


class SalesOrderSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, required=False)

    class Meta:
        model = SalesOrder
        fields = "__all__"
        # Minted by the model on save. Exposed so the app can build the QR link,
        # but never accepted from a client — otherwise anyone could set a known
        # token on someone else's invoice.
        read_only_fields = ["publicToken"]

    def validate(self, attrs):
        """Rules that apply only when a *new* order is being raised (not on
        update, e.g. confirming delivery next day):

        1. Pending employee — a newly-created login (Employee.status ==
           "Pending", not yet activated by an Admin) may not be attributed a
           sale, whether it's placing one for itself or someone else raising
           one on its behalf. Applies even to Manager.
        2. Morning cutoff — sales may only be entered from the shift start
           time onward (CompanySettings.shiftStart). Manager is exempt.
        3. Hierarchy — a DSM/ASM/ASE/FSE may only raise an order for
           themselves or for an Employee in their own downline
           (reports_to chain). Orders attributed to a name/email that isn't
           a linked Employee login (legacy Salesman-only entries) pass
           through unchanged — there's no hierarchy to check them against.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if self.instance is None and user is not None and getattr(user, "is_authenticated", False):
            sr_email = attrs.get("srEmail", "")
            target = Employee.objects.filter(email=sr_email).first() if sr_email else None
            if target is not None and target.status == "Pending":
                raise serializers.ValidationError(
                    {"srEmail": f"{target.name} hasn't been activated yet — an Admin needs to approve them first."}
                )

            if user.role != "Manager":
                company = CompanySettings.load()
                now = timezone.localtime(timezone.now()).strftime("%H:%M")
                if now < company.shiftStart:
                    raise serializers.ValidationError(
                        {"date": f"Sales can only be entered from {company.shiftStart} onward."}
                    )

                if sr_email and sr_email != user.email and target is not None:
                    downline_emails = {e.email for e in user.downline()}
                    if sr_email not in downline_emails:
                        raise serializers.ValidationError(
                            {"srEmail": "You may only record sales for yourself or employees who report to you."}
                        )
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        order = SalesOrder.objects.create(**validated_data)
        for line in lines:
            InvoiceLine.objects.create(order=order, **line)
        return order

    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                InvoiceLine.objects.create(order=instance, **line)
        return instance


class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = "__all__"


class OfferAccrualSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferAccrual
        fields = "__all__"


class SalesmanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salesman
        fields = "__all__"


class AttendanceSerializer(serializers.ModelSerializer):
    """Renames the `in`/`out` JSON keys (Python keywords) to the model's
    check_in/check_out fields, and exposes sr_id as `id` to match the frontend
    AttendanceRow shape.

    Also owns the shift rules: whatever `status` a client sends, the server
    recomputes Present / Late Present / Early Out from the punch times against
    the configured window. That keeps a hand-edited row and a phone check-in
    honest with each other, and means the rule lives in exactly one place.
    """

    class Meta:
        model = Attendance
        fields = [
            "pk", "sr_id", "name", "email", "check_in", "check_out",
            "status", "visits", "date", "inLoc", "outLoc",
            "lateMinutes", "earlyMinutes",
        ]
        # Derived server-side from the punch times; a client can't set them.
        read_only_fields = ["lateMinutes", "earlyMinutes"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {
            "pk": data["pk"],
            "id": data["sr_id"],
            "name": data["name"],
            "email": data["email"],
            "in": data["check_in"],
            "out": data["check_out"],
            "status": data["status"],
            "visits": data["visits"],
            "date": data["date"],
            "inLoc": data["inLoc"],
            "outLoc": data["outLoc"],
            "lateMinutes": data["lateMinutes"],
            "earlyMinutes": data["earlyMinutes"],
        }

    def to_internal_value(self, data):
        mapped = dict(data)
        if "id" in mapped:
            mapped["sr_id"] = mapped.pop("id")
        if "in" in mapped:
            mapped["check_in"] = mapped.pop("in")
        if "out" in mapped:
            mapped["check_out"] = mapped.pop("out")
        return super().to_internal_value(mapped)

    def validate(self, attrs):
        """Apply the shift window to whatever the punch times end up being.

        On a PATCH only some keys are present, so fall back to the instance for
        the rest — otherwise recording a check-out would evaluate against an
        empty check-in and wrongly clear a Late Present flag.
        """
        instance = getattr(self, "instance", None)

        def current(field, default=""):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        company = CompanySettings.load()
        status, late, early = evaluate_shift(
            current("check_in"),
            current("check_out"),
            company=company,
            current_status=current("status"),
        )
        attrs["status"] = status
        attrs["lateMinutes"] = late
        attrs["earlyMinutes"] = early

        if status in LEAVE_QUOTA:
            email = current("email")
            employee = Employee.objects.filter(email=email).first() if email else None
            leave_date = _parse_iso_date(current("date"))
            if employee is not None and leave_date is not None:
                eligible_from = leave_eligible_from(employee.joining_date)
                if leave_date < eligible_from:
                    raise serializers.ValidationError(
                        {"status": f"{employee.name} becomes eligible for leave on {eligible_from.isoformat()} (6 months after joining)."}
                    )
                quota = LEAVE_QUOTA[status]
                used = Attendance.objects.filter(
                    email=email, status=status, date__startswith=str(leave_date.year)
                ).exclude(pk=getattr(instance, "pk", None)).count()
                if used >= quota:
                    raise serializers.ValidationError(
                        {"status": f"{employee.name} has already used all {quota} {status} day(s) for {leave_date.year}."}
                    )
        return attrs


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = "__all__"


class VisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visit
        fields = "__all__"


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class CashbackTxnSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashbackTxn
        fields = "__all__"


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = "__all__"


class ShopReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopReview
        fields = "__all__"


# ---------------------------------------------------------------------------
# Settings / master data
# ---------------------------------------------------------------------------
class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "active"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "active"]


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "active"]


class ProductSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSegment
        fields = ["id", "name", "active"]


class AccountHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountHead
        fields = ["id", "name", "active"]


class ExpenseHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseHead
        fields = ["id", "name", "active"]


class ShopCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopCategory
        fields = ["id", "name", "active"]


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name", "active"]


class AreaSerializer(serializers.ModelSerializer):
    # Optional — an Area doesn't have to belong to a Region yet.
    region = serializers.SlugRelatedField(
        slug_field="name", queryset=Region.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Area
        fields = ["id", "name", "zone", "code", "region", "active"]


class TerritorySerializer(serializers.ModelSerializer):
    """`area` is the area's *name* in both directions, so the React form can
    filter territories by the selected area without resolving ids."""

    area = serializers.SlugRelatedField(slug_field="name", queryset=Area.objects.all())

    class Meta:
        model = Territory
        fields = ["id", "name", "code", "area", "active"]

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", None))
        area = attrs.get("area", getattr(self.instance, "area", None))
        qs = Territory.objects.filter(name=name, area=area)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"name": f"'{name}' already exists in {area}."}
            )
        return attrs


class DealerSerializer(serializers.ModelSerializer):
    """`region`/`area`/`territory` are plain names (see the model docstring).
    `area_code`/`territory_code` are resolved read-only from the matching
    Settings master-list entry, by name, at read time — so a code change on
    the Area/Territory list is reflected immediately without touching every
    dealer that references it. `ase_name` is resolved from the linked
    Employee for display; `ase` itself *is* that employee's id_no."""

    ase_name = serializers.CharField(source="ase.name", read_only=True, default="")
    area_code = serializers.SerializerMethodField()
    territory_code = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "code", "name", "region", "area", "area_code", "territory", "territory_code",
            "ase", "ase_name", "contact_number", "address", "createdAt",
        ]
        read_only_fields = ["createdAt"]

    def get_area_code(self, obj):
        area = Area.objects.filter(name=obj.area).first()
        return area.code if area else ""

    def get_territory_code(self, obj):
        territory = Territory.objects.filter(name=obj.territory, area__name=obj.area).first()
        return territory.code if territory else ""


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = [
            "id", "name", "tagline", "logo", "address", "phone", "email",
            "website", "currency", "vatBin", "invoiceFooter",
            "loginImage1", "loginImage2",
            "shiftStart", "shiftEnd",
        ]
        read_only_fields = ["id"]

    def validate_shiftStart(self, value):
        return self._validate_time(value, "Shift start")

    def validate_shiftEnd(self, value):
        return self._validate_time(value, "Shift end")

    @staticmethod
    def _validate_time(value, label):
        from .attendance_rules import to_minutes

        if to_minutes(value) is None:
            raise serializers.ValidationError(f"{label} must look like 10:05 (24-hour).")
        return value


class DamageRecordSerializer(serializers.ModelSerializer):
    """Validates a write-off and fills in the snapshot fields.

    The client normally sends the snapshots (productName, pcs_per_carton,
    damaged_pcs, loss_value) because it is the client that also debits the
    product's good stock. They are re-derived here from the referenced product
    whenever they are missing or zero, so a record created straight from the
    API or the admin is still complete and still reversible.
    """

    class Meta:
        model = DamageRecord
        fields = "__all__"

    def validate_quantity(self, value):
        if value is None or int(value) <= 0:
            raise serializers.ValidationError("Damaged quantity must be at least 1.")
        return value

    def validate(self, attrs):
        data = {**getattr(self.instance, "__dict__", {}), **attrs} if self.instance else dict(attrs)
        sku = data.get("sku")
        product = Product.objects.filter(sku=sku).first() if sku else None
        if sku and product is None:
            raise serializers.ValidationError({"sku": "No product with that SKU."})
        if product is None:
            return attrs

        unit_type = data.get("unit_type") or product.unit_type or "PCS"
        quantity = int(data.get("quantity") or 0)
        pcs_per_carton = int(data.get("pcs_per_carton") or 0) or max(1, product.pcs_per_carton or 1)
        damaged_pcs = int(data.get("damaged_pcs") or 0) or (
            quantity * pcs_per_carton if unit_type == "Carton" else quantity
        )

        if product.unit_type == "Carton":
            price_per_pcs = Decimal(product.cartonPrice or 0) / Decimal(pcs_per_carton)
        else:
            price_per_pcs = Decimal(product.price or 0)

        if not attrs.get("productName"):
            attrs["productName"] = product.name
        attrs["unit_type"] = unit_type
        attrs["pcs_per_carton"] = pcs_per_carton
        attrs["damaged_pcs"] = damaged_pcs
        if not data.get("loss_value"):
            attrs["loss_value"] = (price_per_pcs * Decimal(damaged_pcs)).quantize(Decimal("0.01"))
        return attrs


class StockEntrySerializer(serializers.ModelSerializer):
    """Validates a restock and fills in the snapshot fields — the mirror of
    DamageRecordSerializer above, same reasoning: the client normally sends
    the snapshots because it's also the client that credits the product's
    good stock, but they're re-derived here whenever missing so a record
    created straight from the API or the admin is still complete."""

    class Meta:
        model = StockEntry
        fields = "__all__"

    def validate_quantity(self, value):
        if value is None or int(value) <= 0:
            raise serializers.ValidationError("Restock quantity must be at least 1.")
        return value

    def validate(self, attrs):
        data = {**getattr(self.instance, "__dict__", {}), **attrs} if self.instance else dict(attrs)
        sku = data.get("sku")
        product = Product.objects.filter(sku=sku).first() if sku else None
        if sku and product is None:
            raise serializers.ValidationError({"sku": "No product with that SKU."})
        if product is None:
            return attrs

        unit_type = data.get("unit_type") or product.unit_type or "PCS"
        quantity = int(data.get("quantity") or 0)
        pcs_per_carton = int(data.get("pcs_per_carton") or 0) or max(1, product.pcs_per_carton or 1)
        added_pcs = int(data.get("added_pcs") or 0) or (
            quantity * pcs_per_carton if unit_type == "Carton" else quantity
        )

        if not attrs.get("productName"):
            attrs["productName"] = product.name
        attrs["unit_type"] = unit_type
        attrs["pcs_per_carton"] = pcs_per_carton
        attrs["added_pcs"] = added_pcs
        return attrs


# ---------------------------------------------------------------------------
# HR Module Serializers
# ---------------------------------------------------------------------------
class PromotionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PromotionHistory
        fields = "__all__"


class EmployeeRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeReward
        fields = "__all__"


class EmployeePunishmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeePunishment
        fields = "__all__"


class EmployeeSerializer(serializers.ModelSerializer):
    """Employee *is* the login account (core.Employee is AUTH_USER_MODEL) —
    there's no separate accounts.User to keep in sync. `password` overrides
    the real (hashed) model field so it's write-only and never echoed back;
    create()/update() route it through set_password() instead of storing it
    as plain text."""

    age = serializers.ReadOnlyField()  # Computed property
    years_of_service = serializers.ReadOnlyField()  # Computed property
    promotions = PromotionHistorySerializer(many=True, read_only=True)  # Nested promotion history
    rewards = EmployeeRewardSerializer(many=True, read_only=True)  # Nested rewards
    punishments = EmployeePunishmentSerializer(many=True, read_only=True)  # Nested punishments

    password = serializers.CharField(write_only=True, required=False, allow_blank=True, style={"input_type": "password"})
    reports_to_name = serializers.CharField(source="reports_to.name", read_only=True, default="")

    class Meta:
        model = Employee
        fields = [
            "id_no", "name", "email", "password",
            "fathers_name", "mothers_name", "date_of_birth", "home_district", "permanent_address",
            "designation", "branch", "status", "joining_date", "salary",
            "reports_to", "reports_to_name",
            "promotion_history_count", "particulars_rewards", "particulars_punishment",
            "age", "years_of_service", "is_active",
            "created_at", "updated_at",
            "promotions", "rewards", "punishments",
        ]
        read_only_fields = ["promotion_history_count", "created_at", "updated_at"]

    #: Fields only Manager/HR (or the employee themselves) ever see. Everyone
    #: else still needs the *rest* of this serializer — name/email/
    #: designation/reports_to — since pickers across the app (sales officer,
    #: Reports To, attendance display names) read the full employee list.
    _SENSITIVE_FIELDS = [
        "fathers_name", "mothers_name", "date_of_birth", "home_district", "permanent_address",
        "salary", "promotion_history_count", "particulars_rewards", "particulars_punishment",
        "promotions", "rewards", "punishments",
    ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        is_self = user is not None and getattr(user, "pk", None) == instance.pk
        if user is not None and (is_self or user.role in ("Manager", "HR")):
            return data
        for field in self._SENSITIVE_FIELDS:
            data.pop(field, None)
        return data

    def validate(self, attrs):
        # Every employee needs a login, so both are required on create. On
        # update they're optional — leave email/password untouched to keep
        # the existing login as-is.
        if self.instance is None:
            if not attrs.get("email"):
                raise serializers.ValidationError({"email": "Email is required."})
            if not attrs.get("password"):
                raise serializers.ValidationError({"password": "Password is required."})
        else:
            request = self.context.get("request")
            actor = getattr(request, "user", None) if request else None

            # HR may onboard a new hire with a designation, but changing an
            # *existing* employee's role afterward — a promotion, demotion,
            # or transfer — is a Super Admin (Manager) decision, not an HR one.
            new_designation = attrs.get("designation")
            if new_designation and new_designation != self.instance.designation:
                if actor is not None and actor.role != "Manager":
                    raise serializers.ValidationError(
                        {"designation": "Only a Super Admin (Manager) may change an employee's role/designation."}
                    )

            # Likewise, HR can add and edit employee information, but resetting
            # an *existing* login's password is Super Admin-only. (HR still
            # sets the initial password when onboarding a new hire, above.)
            if attrs.get("password"):
                if actor is not None and actor.role != "Manager":
                    raise serializers.ValidationError(
                        {"password": "Only a Super Admin (Manager) may change a password."}
                    )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        employee = Employee(**validated_data)
        employee.set_password(password)
        employee.save()
        return employee

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
