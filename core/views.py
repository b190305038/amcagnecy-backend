import secrets
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response

from accounts.permissions import RoleModulePermission

from .importexport import XLSX_CONTENT_TYPE, build_csv, build_xlsx, parse_upload
from .sales_report import build_report, build_report_xlsx
from .specs import (
    ATTENDANCE_SPEC,
    CASHBACK_SPEC,
    DEALER_SPEC,
    EMPLOYEE_SPEC,
    OFFER_SPEC,
    PAYMENT_SPEC,
    PRODUCT_SPEC,
    SALESMAN_SPEC,
    SALES_ORDER_SPEC,
    SHOP_SPEC,
    TARGET_SPEC,
    VISIT_SPEC,
    next_dealer_code,
    next_employee_id,
    next_salesman_id,
    next_shop_code,
)

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
    ShopReview,
    Target,
    Territory,
    Unit,
    Visit,
)
from .serializers import (
    AccountHeadSerializer,
    AreaSerializer,
    AttendanceSerializer,
    BrandSerializer,
    CashbackTxnSerializer,
    CompanySettingsSerializer,
    DamageRecordSerializer,
    DealerSerializer,
    EmployeePunishmentSerializer,
    EmployeeRewardSerializer,
    EmployeeSerializer,
    ExpenseHeadSerializer,
    LedgerEntrySerializer,
    OfferAccrualSerializer,
    OfferSerializer,
    PaymentSerializer,
    PayoutSerializer,
    ProductCategorySerializer,
    ProductSegmentSerializer,
    ProductSerializer,
    PromotionHistorySerializer,
    RegionSerializer,
    SalesOrderSerializer,
    SalesmanSerializer,
    ShopCategorySerializer,
    ShopReviewSerializer,
    ShopSerializer,
    TargetSerializer,
    TerritorySerializer,
    UnitSerializer,
    VisitSerializer,
)


class BaseViewSet(viewsets.ModelViewSet):
    """All collections share role-based permissions + pagination/search/order."""

    permission_classes = [RoleModulePermission]


# ---------------------------------------------------------------------------
# Bulk import / export
# ---------------------------------------------------------------------------
class ImportExportMixin:
    """Adds /template/, /export/ and /import/ to a viewset.

    Set `spec` to a Spec from core.specs. The three routes share that one column
    definition, so a file exported from /export/ imports cleanly through
    /import/ without the user editing headers.
    """

    spec = None
    #: Optional callable returning the next primary key for a row that arrived
    #: without one, so bulk-created records follow the app's own id scheme.
    generate_id = None

    def _spec(self):
        if self.spec is None:  # pragma: no cover - guarded by wiring, not input
            raise NotImplementedError("Set `spec` on the viewset to enable import/export.")
        return self.spec

    def _file_response(self, payload, filename, fmt):
        if fmt == "csv":
            response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
        else:
            response = HttpResponse(payload, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        # The browser fetch() needs this to read the filename back off the response.
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response

    @staticmethod
    def _format(request):
        """Which file format to emit: "xlsx" (default) or "csv".

        Deliberately NOT called `format`: DRF reserves that query parameter for
        renderer selection (URL_FORMAT_OVERRIDE), so `?format=xlsx` never
        reaches the view — content negotiation fails to find an "xlsx" renderer
        and returns a bare 404 instead.
        """
        fmt = (request.query_params.get("ext") or "xlsx").lower()
        return "csv" if fmt == "csv" else "xlsx"

    @action(detail=False, methods=["get"])
    def template(self, request):
        """Blank workbook: styled headers, dropdowns, sample row, instructions."""
        spec = self._spec()
        fmt = self._format(request)
        payload = (
            build_csv(spec, [], template=True)
            if fmt == "csv"
            else build_xlsx(spec, [], template=True)
        )
        return self._file_response(payload, f"{spec.filename}-import-template.{fmt}", fmt)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Every row the caller can see, in the template's column order.

        Runs through the viewset's own filter backends, so whatever the user has
        narrowed the list to on screen is what lands in the file.
        """
        spec = self._spec()
        fmt = self._format(request)
        queryset = self.filter_queryset(self.get_queryset())
        rows = list(queryset.values(*[c.key for c in spec.columns]))
        payload = (
            build_csv(spec, rows, template=False)
            if fmt == "csv"
            else build_xlsx(spec, rows, template=False)
        )
        stamp = date.today().isoformat()
        return self._file_response(payload, f"{spec.filename}-{stamp}.{fmt}", fmt)

    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="import",
    )
    def import_rows(self, request):
        """Upsert an uploaded .xlsx/.csv.

        A row with a known primary key updates that record; a row without one is
        created. Bad rows are reported by line number and skipped so a single
        typo never blocks a 500-row upload. The whole run is one transaction —
        if the database rejects something mid-way, nothing is half-applied.
        """
        spec = self._spec()
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "Attach a file to import."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows, row_errors = parse_upload(upload, spec)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        model = self.get_queryset().model
        created = updated = 0
        failed = list(row_errors)

        with transaction.atomic():
            for index, row in enumerate(rows, start=1):
                key = str(row.get(spec.id_field) or "").strip()
                try:
                    if key and model.objects.filter(**{spec.id_field: key}).exists():
                        payload = {k: v for k, v in row.items() if k != spec.id_field}
                        model.objects.filter(**{spec.id_field: key}).update(**payload)
                        updated += 1
                    else:
                        if not key and callable(self.generate_id):
                            row[spec.id_field] = self.generate_id()
                        model.objects.create(**row)
                        created += 1
                except Exception as exc:  # noqa: BLE001 - surfaced to the user
                    failed.append({"row": index + 1, "errors": [str(exc)]})

        return Response(
            {
                "created": created,
                "updated": updated,
                "skipped": len(failed),
                # Cap the payload so a wholly malformed file doesn't return a
                # megabyte of errors the UI can't display anyway.
                "errors": failed[:50],
                "detail": f"Imported {created} new and {updated} updated record(s).",
            }
        )


class ProductViewSet(ImportExportMixin, BaseViewSet):
    module = "products"
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    search_fields = ["sku", "name", "category", "brand", "unit_type"]
    filterset_fields = ["category", "brand", "unit", "unit_type"]
    ordering_fields = ["sku", "name", "price", "stock", "unit_type"]
    spec = PRODUCT_SPEC


class TargetViewSet(ImportExportMixin, BaseViewSet):
    module = "targets"
    queryset = Target.objects.all()
    serializer_class = TargetSerializer
    search_fields = ["name", "description", "status"]
    filterset_fields = ["status", "honorarium_type"]
    ordering_fields = ["name", "target_value", "start_date", "end_date", "status"]
    spec = TARGET_SPEC


class ShopViewSet(ImportExportMixin, BaseViewSet):
    module = "shops"
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    search_fields = ["code", "name", "owner", "area", "territory", "srName", "srEmail"]
    filterset_fields = ["category", "area", "territory", "zone", "district", "thana", "srEmail"]
    ordering_fields = ["code", "name", "sales30d", "due", "credit"]
    spec = SHOP_SPEC
    generate_id = staticmethod(next_shop_code)


class SalesOrderViewSet(ImportExportMixin, BaseViewSet):
    module = "sales"
    queryset = SalesOrder.objects.prefetch_related("lines").all()
    serializer_class = SalesOrderSerializer
    search_fields = ["id", "shop", "sr", "bkashTxn", "offer"]
    filterset_fields = ["shop", "sr", "srEmail", "payment", "status", "offer", "date"]
    ordering_fields = ["date", "amount", "id"]
    spec = SALES_ORDER_SPEC


class OfferViewSet(ImportExportMixin, BaseViewSet):
    module = "offers"
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    search_fields = ["id", "name", "type", "reward"]
    filterset_fields = ["type", "status"]
    ordering_fields = ["id", "name", "accrued", "start", "end"]
    spec = OFFER_SPEC


class OfferAccrualViewSet(BaseViewSet):
    # Its own module so a sale can accrue against an offer without granting the
    # seller rights to edit the offer definitions themselves.
    module = "offer-accruals"
    queryset = OfferAccrual.objects.all()
    serializer_class = OfferAccrualSerializer
    search_fields = ["shop", "offer"]
    filterset_fields = ["shop", "offer", "status"]
    ordering_fields = ["shop", "accrued", "purchases"]


class DamageRecordViewSet(BaseViewSet):
    # Reuses the "products" module's permissions — anyone who can write
    # products can log a damage/write-off against the same stock.
    module = "products"
    queryset = DamageRecord.objects.all()
    serializer_class = DamageRecordSerializer
    search_fields = ["id", "sku", "productName", "reason", "note"]
    filterset_fields = ["sku", "reason", "date"]
    ordering_fields = ["date", "quantity", "loss_value"]


class SalesmanViewSet(ImportExportMixin, BaseViewSet):
    module = "targets"
    queryset = Salesman.objects.all()
    serializer_class = SalesmanSerializer
    search_fields = ["id", "name", "area", "territory"]
    filterset_fields = ["area", "territory"]
    ordering_fields = ["id", "name", "target", "achieved", "commission"]
    spec = SALESMAN_SPEC
    generate_id = staticmethod(next_salesman_id)


class AttendanceViewSet(ImportExportMixin, BaseViewSet):
    module = "attendance"
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    search_fields = ["sr_id", "name", "email", "status"]
    filterset_fields = ["status", "date", "sr_id"]
    ordering_fields = ["sr_id", "name", "visits"]
    spec = ATTENDANCE_SPEC


class LedgerEntryViewSet(BaseViewSet):
    module = "accounting"
    queryset = LedgerEntry.objects.all()
    serializer_class = LedgerEntrySerializer
    search_fields = ["account", "type", "ref"]
    filterset_fields = ["type", "date", "account"]
    ordering_fields = ["date", "debit", "credit"]


class VisitViewSet(ImportExportMixin, BaseViewSet):
    module = "visits"
    queryset = Visit.objects.all()
    serializer_class = VisitSerializer
    search_fields = ["sr", "shop", "outcome", "note"]
    filterset_fields = ["sr", "srId", "shop", "outcome"]
    ordering_fields = ["id", "time"]
    spec = VISIT_SPEC


class PaymentViewSet(ImportExportMixin, BaseViewSet):
    # Written by both the sales flow and the accounting flow (see DERIVED).
    module = "payments"
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    search_fields = ["id", "invoiceId", "shop", "txn"]
    filterset_fields = ["shop", "method", "invoiceId", "date"]
    ordering_fields = ["date", "amount", "id"]
    spec = PAYMENT_SPEC


class CashbackTxnViewSet(ImportExportMixin, BaseViewSet):
    module = "cashback"
    queryset = CashbackTxn.objects.all()
    serializer_class = CashbackTxnSerializer
    search_fields = ["id", "shop", "offer", "invoiceId"]
    filterset_fields = ["shop", "type", "offer", "date"]
    ordering_fields = ["date", "amount", "id"]
    spec = CASHBACK_SPEC


class PayoutViewSet(BaseViewSet):
    # Reimbursements to shops. Tagged to the "payments" module so finance roles
    # (Accountant, managers) may record them, same as invoice payments.
    module = "payments"
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer
    search_fields = ["id", "shop", "offer", "method", "note"]
    filterset_fields = ["shop", "method", "offer", "date"]
    ordering_fields = ["date", "amount", "id"]


class ShopReviewViewSet(BaseViewSet):
    # Reviews attach to a customer (shop), so they ride the "shops" module: any
    # role that may write shops may leave a review.
    module = "shops"
    queryset = ShopReview.objects.all()
    serializer_class = ShopReviewSerializer
    search_fields = ["shop", "sentiment", "note", "author"]
    filterset_fields = ["shop", "sentiment", "date"]
    ordering_fields = ["date", "id"]


# ---------------------------------------------------------------------------
# Settings / master data
#
# module="settings" is granted to no role but Super Admin (whose "*" covers it),
# so every other role gets read-only access - which is all they need, since the
# lists only feed dropdowns in the Product and Shop forms.
# ---------------------------------------------------------------------------
class SettingsViewSet(BaseViewSet):
    module = "settings"
    search_fields = ["name"]
    ordering_fields = ["name"]

    def destroy(self, request, *args, **kwargs):
        """Turn a PROTECT violation into a readable 400 instead of a 500.

        Deleting an Area that still has territories would otherwise blow up with
        an unhandled ProtectedError.
        """
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as exc:
            blockers = sorted({str(obj) for obj in exc.protected_objects})[:5]
            return Response(
                {
                    "detail": (
                        "This entry is still in use and can't be deleted. "
                        "Set it inactive instead, or remove what depends on it first."
                    ),
                    "used_by": blockers,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class BrandViewSet(SettingsViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    filterset_fields = ["active"]


class UnitViewSet(SettingsViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    filterset_fields = ["active"]


class ProductCategoryViewSet(SettingsViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    filterset_fields = ["active"]


class ProductSegmentViewSet(SettingsViewSet):
    queryset = ProductSegment.objects.all()
    serializer_class = ProductSegmentSerializer
    filterset_fields = ["active"]


class AccountHeadViewSet(SettingsViewSet):
    queryset = AccountHead.objects.all()
    serializer_class = AccountHeadSerializer
    filterset_fields = ["active"]


class ExpenseHeadViewSet(SettingsViewSet):
    queryset = ExpenseHead.objects.all()
    serializer_class = ExpenseHeadSerializer
    filterset_fields = ["active"]


class ShopCategoryViewSet(SettingsViewSet):
    queryset = ShopCategory.objects.all()
    serializer_class = ShopCategorySerializer
    filterset_fields = ["active"]


class RegionViewSet(SettingsViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    filterset_fields = ["active"]


class AreaViewSet(SettingsViewSet):
    queryset = Area.objects.select_related("region").all()
    serializer_class = AreaSerializer
    search_fields = ["name", "zone", "code"]
    filterset_fields = ["active", "zone", "region"]


class TerritoryViewSet(SettingsViewSet):
    queryset = Territory.objects.select_related("area").all()
    serializer_class = TerritorySerializer
    search_fields = ["name", "area__name", "code"]
    filterset_fields = ["active", "area"]
    ordering_fields = ["name", "area__name"]


class DealerViewSet(ImportExportMixin, BaseViewSet):
    module = "shops"
    queryset = Dealer.objects.select_related("ase").all()
    serializer_class = DealerSerializer
    search_fields = ["code", "name", "region", "area", "territory", "contact_number", "address"]
    filterset_fields = ["region", "area", "territory", "ase"]
    ordering_fields = ["code", "name", "createdAt"]
    spec = DEALER_SPEC
    generate_id = staticmethod(next_dealer_code)


class CompanySettingsViewSet(SettingsViewSet):
    """Always exactly one row. The frontend treats it as a one-item collection.

    Branding (name, tagline, logo) needs to render on the public Login page
    before anyone has signed in, so reads are open to anyone. Writes still go
    through the normal role-based settings permission — only roles allowed to
    edit "settings" can change the company row.
    """

    serializer_class = CompanySettingsSerializer
    pagination_class = None
    search_fields = []
    ordering_fields = []
    filterset_fields = []

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        CompanySettings.load()  # create the singleton on first access
        return CompanySettings.objects.all()


# ---------------------------------------------------------------------------
# Public invoice view (QR code target)
#
# The QR printed on an invoice encodes <frontend>/invoice/<id>?t=<publicToken>.
# A shop owner scans it on their own phone with no account, so this endpoint is
# deliberately unauthenticated — the token is the credential. It returns only
# what belongs on the paper the customer is already holding: the line items,
# the totals, the payment state, and the company's identity. No cost prices, no
# other shops, no staff contact details.
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def public_invoice(request, invoice_id):
    token = (request.query_params.get("t") or "").strip()
    if not token:
        return Response(
            {"detail": "This invoice link is incomplete. Scan the QR code on the invoice again."},
            status=status.HTTP_403_FORBIDDEN,
        )

    order = SalesOrder.objects.prefetch_related("lines").filter(id=invoice_id).first()
    # One shared message for "no such invoice" and "wrong token" so the endpoint
    # can't be used to confirm which invoice numbers exist.
    if order is None or not order.publicToken or not secrets.compare_digest(order.publicToken, token):
        return Response(
            {"detail": "This invoice link is not valid. Please ask the agency for a fresh copy."},
            status=status.HTTP_404_NOT_FOUND,
        )

    company = CompanySettings.load()
    shop = Shop.objects.filter(name=order.shop).first()

    # Paid / due are recomputed from the payment log rather than trusted from the
    # order row, so a scanned invoice always shows the true current balance.
    paid = sum(
        (p.amount for p in Payment.objects.filter(invoiceId=order.id)),
        Decimal("0"),
    )
    total = Decimal(order.amount or 0)
    due = max(Decimal("0"), total - paid)
    if due <= 0:
        pay_status = "Paid"
    elif paid > 0:
        pay_status = "Partial"
    else:
        pay_status = "Due"

    return Response(
        {
            "invoice": {
                "id": order.id,
                "date": order.date,
                "shop": order.shop,
                "sr": order.sr,
                "items": order.items,
                "amount": total,
                "gross": order.gross,
                "discount": order.discount,
                "paid": paid,
                "due": due,
                "payment": order.payment,
                "status": pay_status,
                "stage": order.stage,
                "deliveredDate": order.deliveredDate,
                "offer": order.offer,
                "lines": [
                    {"sku": l.sku, "name": l.name, "qty": l.qty, "price": l.price}
                    for l in order.lines.all()
                ],
            },
            "shop": {
                "name": order.shop,
                "owner": getattr(shop, "owner", ""),
                "address": getattr(shop, "address", ""),
                "phone": getattr(shop, "phone", ""),
            },
            "company": {
                "name": company.name,
                "tagline": company.tagline,
                "logo": company.logo,
                "address": company.address,
                "phone": company.phone,
                "email": company.email,
                "website": company.website,
                "currency": company.currency,
                "vatBin": company.vatBin,
                "invoiceFooter": company.invoiceFooter,
            },
        }
    )


# ---------------------------------------------------------------------------
# MTD / YTD product-wise sales report — one row per Dealer, a Volume + Value
# column pair per product. GET for the on-screen table, GET ?ext=xlsx to
# download the same data as the client's Excel template.
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([RoleModulePermission])
def product_sales_report(request):
    as_of_param = (request.query_params.get("as_of") or "").strip()
    try:
        as_of = date.fromisoformat(as_of_param) if as_of_param else date.today()
    except ValueError:
        return Response({"detail": "as_of must be a YYYY-MM-DD date."}, status=status.HTTP_400_BAD_REQUEST)

    report = build_report(
        as_of,
        region=(request.query_params.get("region") or "").strip(),
        area=(request.query_params.get("area") or "").strip(),
        territory=(request.query_params.get("territory") or "").strip(),
    )

    if (request.query_params.get("ext") or "").lower() == "xlsx":
        payload = build_report_xlsx(report)
        response = HttpResponse(payload, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f'attachment; filename="mtd-ytd-sales-{report["asOf"]}.xlsx"'
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response

    return Response(report)


# ---------------------------------------------------------------------------
# HR Module ViewSets
# ---------------------------------------------------------------------------
class EmployeeViewSet(ImportExportMixin, BaseViewSet):
    """Employee CRUD *is* login/account management — core.Employee is
    settings.AUTH_USER_MODEL (see core/models.py), so there's no separate
    user record to keep in sync. EmployeeSerializer.create()/update() already
    hash the password field; the default ModelViewSet create/update/destroy
    need no overriding here.
    """

    module = "hr"
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    search_fields = ["id_no", "name", "email", "designation"]
    filterset_fields = ["designation", "joining_date"]
    ordering_fields = ["id_no", "name", "designation", "joining_date", "salary"]
    spec = EMPLOYEE_SPEC
    generate_id = staticmethod(next_employee_id)


class PromotionHistoryViewSet(BaseViewSet):
    module = "hr"
    queryset = PromotionHistory.objects.all()
    serializer_class = PromotionHistorySerializer
    search_fields = ["id", "employee__name", "promotion_type"]
    filterset_fields = ["employee", "promotion_type", "promotion_date"]
    ordering_fields = ["promotion_date", "employee__name"]


class EmployeeRewardViewSet(BaseViewSet):
    module = "hr"
    queryset = EmployeeReward.objects.all()
    serializer_class = EmployeeRewardSerializer
    search_fields = ["id", "employee__name", "reward_type", "description"]
    filterset_fields = ["employee", "reward_type", "date"]
    ordering_fields = ["date", "employee__name"]


class EmployeePunishmentViewSet(BaseViewSet):
    module = "hr"
    queryset = EmployeePunishment.objects.all()
    serializer_class = EmployeePunishmentSerializer
    search_fields = ["id", "employee__name", "severity", "offense"]
    filterset_fields = ["employee", "severity", "date"]
    ordering_fields = ["date", "employee__name", "severity"]
