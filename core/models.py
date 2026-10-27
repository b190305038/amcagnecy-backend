"""
Business models for the sales-monitoring app.

Field names deliberately mirror the frontend TypeScript types in
`src/lib/types.ts` so the JSON the API returns matches what the React app
already expects. Money is stored as Decimal; DRF is configured with
COERCE_DECIMAL_TO_STRING=False so it serializes as a JSON number.
"""
import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

MONEY = dict(max_digits=16, decimal_places=2)


def new_public_token() -> str:
    """Unguessable token embedded in the invoice QR link.

    Invoice ids are sequential (INV-24061, INV-24062 …) so the id alone can be
    walked by anyone who scans a single invoice. The token turns the printed QR
    into a capability: you can only open the invoice you were handed.
    """
    return secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# Master data (Settings module)
#
# These replace the hardcoded constants that used to live in the React pages
# (BRANDS/UNITS/CATEGORIES in products.tsx, AREAS/TERRITORIES in shops.tsx and
# targets.tsx). Products and Shops store their category/brand/area as plain
# text, so deleting a list entry never orphans a record - it just stops being
# offered in the dropdown. `active=False` retires an entry without deleting it.
# ---------------------------------------------------------------------------
class MasterListEntry(models.Model):
    """Shared behaviour for the simple name-only lookup lists."""

    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(MasterListEntry):
    pass


class Unit(MasterListEntry):
    name = models.CharField(max_length=40, unique=True)


class ProductCategory(MasterListEntry):
    class Meta(MasterListEntry.Meta):
        verbose_name_plural = "product categories"


class ProductSegment(MasterListEntry):
    class Meta(MasterListEntry.Meta):
        verbose_name_plural = "product segments"


class ShopCategory(MasterListEntry):
    class Meta(MasterListEntry.Meta):
        verbose_name_plural = "shop categories"


class AccountHead(MasterListEntry):
    """Top-level accounting head: Income / Expense / Asset / Liability / Equity.
    Feeds the Type dropdown on the Accounting ledger form."""

    class Meta(MasterListEntry.Meta):
        verbose_name_plural = "account heads"


class ExpenseHead(MasterListEntry):
    """Expense category (Salaries & Wages, Utility Bill, …). Offered as the
    Account options on the ledger form when the head is Expense."""

    class Meta(MasterListEntry.Meta):
        verbose_name_plural = "expense heads"


class Region(MasterListEntry):
    """Top of the sales geography hierarchy: Region -> Area -> Territory."""

    pass


class Area(MasterListEntry):
    # Optional higher-level grouping, matching the `zone` field on Shop.
    zone = models.CharField(max_length=120, blank=True, default="")
    code = models.CharField(max_length=40, blank=True, default="")
    region = models.ForeignKey(
        Region, related_name="areas", on_delete=models.SET_NULL, null=True, blank=True
    )


class Territory(models.Model):
    """A territory always belongs to an area; the Shop form filters on it."""

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, blank=True, default="")
    area = models.ForeignKey(Area, related_name="territories", on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["area__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "area"], name="unique_territory_per_area"),
        ]

    def __str__(self):
        return f"{self.name} ({self.area.name})"


class CompanySettings(models.Model):
    """Single row (pk=1) holding company identity used across the UI."""

    name = models.CharField(max_length=200, default="A.M.C. Agency")
    tagline = models.CharField(max_length=200, blank=True, default="")
    logo = models.TextField(blank=True, default="")  # data URL or image URL
    address = models.CharField(max_length=400, blank=True, default="")
    phone = models.CharField(max_length=60, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.CharField(max_length=200, blank=True, default="")
    currency = models.CharField(max_length=8, default="৳")  # Bangladeshi taka
    vatBin = models.CharField(max_length=60, blank=True, default="")
    invoiceFooter = models.CharField(max_length=400, blank=True, default="")

    # Two images shown side by side on the sign-in screen. Blank hides them.
    loginImage1 = models.TextField(blank=True, default="")  # data URL or image URL
    loginImage2 = models.TextField(blank=True, default="")  # data URL or image URL

    # -- Attendance shift window -------------------------------------------
    # Stored as "HH:MM" 24-hour strings so they compare lexicographically the
    # same way they compare chronologically. A check-in at or before shiftStart
    # is Present; later is "Late Present". A check-out at or after shiftEnd is a
    # full day; earlier is "Early Out".
    shiftStart = models.CharField(max_length=5, default="10:05")  # 10:05 AM
    shiftEnd = models.CharField(max_length=5, default="19:00")  # 7:00 PM

    class Meta:
        verbose_name_plural = "company settings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Enforce the singleton: there is only ever one company record.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Product(models.Model):
    UNIT_TYPE_CHOICES = [
        ("PCS", "Pieces"),
        ("Carton", "Carton"),
    ]
    sku = models.CharField(max_length=40, primary_key=True)
    name = models.CharField(max_length=200)
    segment = models.CharField(max_length=80, blank=True, default="")
    category = models.CharField(max_length=80)
    brand = models.CharField(max_length=120)
    unit = models.CharField(max_length=40, blank=True, default="")
    unit_type = models.CharField(max_length=10, choices=UNIT_TYPE_CHOICES, default="PCS")
    price = models.DecimalField(**MONEY)
    stock = models.IntegerField(default=0)
    cartonPrice = models.DecimalField(**MONEY, default=0)
    piecePrice = models.DecimalField(**MONEY, default=0)
    cartons = models.IntegerField(default=0)
    pieces = models.IntegerField(default=0)
    pcs_per_carton = models.IntegerField(default=1)
    extra_pcs = models.IntegerField(default=0)
    expiry = models.CharField(max_length=20, blank=True, default="")
    image = models.TextField(blank=True, default="")
    # Set once, automatically, the moment a product is created — lets the
    # Products page show newest-first regardless of SKU or edits later.
    createdAt = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-createdAt", "sku"]

    def __str__(self):
        return f"{self.sku} — {self.name}"

    @property
    def total_pcs(self):
        if self.unit_type == "Carton":
            return (self.cartons * self.pcs_per_carton) + self.extra_pcs
        return self.pieces


class Shop(models.Model):
    code = models.CharField(max_length=40, primary_key=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=80)
    area = models.CharField(max_length=120)
    territory = models.CharField(max_length=120)
    zone = models.CharField(max_length=120, blank=True, default="")
    district = models.CharField(max_length=120, blank=True, default="")
    thana = models.CharField(max_length=120, blank=True, default="")
    owner = models.CharField(max_length=200)
    phone = models.CharField(max_length=60, blank=True, default="")
    address = models.CharField(max_length=400, blank=True, default="")
    credit = models.DecimalField(**MONEY, default=0)
    due = models.DecimalField(**MONEY, default=0)
    sales30d = models.DecimalField(**MONEY, default=0)
    srEmail = models.CharField(max_length=254, blank=True, default="")
    srName = models.CharField(max_length=200, blank=True, default="")
    # The dealer this outlet trades under, for the Region/Area/Territory/ASE
    # roll-up used by the MTD/YTD product-wise sales report. Optional so an
    # outlet can exist before it's assigned to a dealer.
    dealer = models.ForeignKey(
        "Dealer", related_name="shops", on_delete=models.SET_NULL, null=True, blank=True
    )
    createdAt = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-createdAt", "code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Dealer(models.Model):
    """A dealer/distributor account, one level above the individual outlets
    (Shop) it owns. Anchors the Region -> Area -> Territory -> ASE -> Dealer
    hierarchy used by the product-wise sales report and its Excel export.

    Region/Area/Territory are stored as plain text (the *names* of the
    matching Settings master-list entries) rather than foreign keys — the
    same choice already made for Shop.area/Shop.territory and
    Product.category/Product.brand, so renaming or retiring a master-list
    entry never orphans a dealer, and the row stays trivially bulk
    import/export-able as flat text.
    """

    code = models.CharField(max_length=40, primary_key=True)  # e.g. DLR-0001
    name = models.CharField(max_length=200)
    region = models.CharField(max_length=120, blank=True, default="")
    area = models.CharField(max_length=120, blank=True, default="")
    territory = models.CharField(max_length=120, blank=True, default="")
    # The employee covering this dealer — any HR designation (DSM/ASM/ASE/
    # FSE/...), not only field-sales entries in the separate Salesman table.
    # References core.Employee (the HR directory / login account) directly,
    # so the report always reflects whoever HR currently has assigned, and
    # "assign a DSM/ASM" actually has someone to pick from.
    ase = models.ForeignKey(
        "Employee", related_name="dealers", on_delete=models.SET_NULL, null=True, blank=True
    )
    contact_number = models.CharField(max_length=60, blank=True, default="")
    address = models.CharField(max_length=400, blank=True, default="")
    createdAt = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-createdAt", "code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class SalesOrder(models.Model):
    id = models.CharField(max_length=40, primary_key=True)  # e.g. INV-24061
    date = models.CharField(max_length=20)
    shop = models.CharField(max_length=200)
    sr = models.CharField(max_length=200)
    srEmail = models.CharField(max_length=254, blank=True, default="")
    items = models.IntegerField(default=0)
    amount = models.DecimalField(**MONEY, default=0)
    paid = models.DecimalField(**MONEY, default=0)
    due = models.DecimalField(**MONEY, default=0)
    payment = models.CharField(max_length=40)  # Cash | Credit | Bank | bKash | ...
    status = models.CharField(max_length=40)  # Paid | Due | Partial
    bkashTxn = models.CharField(max_length=80, blank=True, default="")
    offer = models.CharField(max_length=200, blank=True, default="")
    # Order lifecycle: an order is placed as "Pending" (delivery usually next day)
    # and becomes "Confirmed" once delivered and payment info is captured.
    stage = models.CharField(max_length=20, default="Pending")  # Pending | Confirmed
    deliveredDate = models.CharField(max_length=20, blank=True, default="")  # ISO date, set on confirm
    # Capability token for the printed QR code. Generated once, never rotated,
    # so a reprint of the same invoice keeps working.
    publicToken = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # Offer calculation snapshot (so the invoice keeps its gross/discount split).
    gross = models.DecimalField(**MONEY, default=0)
    discount = models.DecimalField(**MONEY, default=0)
    # VAT: percent applied to `gross` (before discount), plus the computed
    # amount snapshot — stored rather than re-derived so a changed rate later
    # doesn't alter the amount printed on an already-issued invoice.
    vatPercent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vat = models.DecimalField(**MONEY, default=0)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        # Mint the QR token on first write so every invoice — including ones
        # created before this feature — has a shareable link the moment it exists.
        if not self.publicToken:
            self.publicToken = new_public_token()
        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    order = models.ForeignKey(SalesOrder, related_name="lines", on_delete=models.CASCADE)
    sku = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    qty = models.IntegerField(default=0)
    price = models.DecimalField(**MONEY, default=0)
    # PCS | Carton — snapshotted from the product at sale time (same reasoning
    # as DamageRecord.unit_type/StockEntry.unit_type) so the invoice always
    # prints "2 ctn" vs "2 pcs" correctly, even if the product's own
    # unit_type is changed or the product is deleted later. Blank on invoices
    # created before this field existed — display falls back to looking the
    # product up live for those.
    unit_type = models.CharField(max_length=10, blank=True, default="")

    def __str__(self):
        return f"{self.order_id}: {self.name} x{self.qty}"


class Offer(models.Model):
    id = models.CharField(max_length=40, primary_key=True)  # e.g. OFR-101
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=80)
    start = models.CharField(max_length=20)
    end = models.CharField(max_length=20)
    # eligible may be a string ("All categories") or a list of categories
    eligible = models.JSONField(default=str)
    products = models.JSONField(default=list, blank=True)  # specific product names
    minQty = models.IntegerField(default=0)  # quantity threshold (units of qtyUnit)
    # Offers are added in cartons by default; the form defaults this to "Cartons".
    qtyUnit = models.CharField(max_length=20, blank=True, default="Cartons")  # "" | Cartons | Pieces
    minValue = models.DecimalField(**MONEY, default=0)  # value threshold (৳), independent of qty
    # `reward` is a human-readable label (e.g. "৳ 500"); it is now optional and
    # auto-derived on the form from the numeric rewardAmount below.
    reward = models.CharField(max_length=200, blank=True, default="")
    # Reward value in taka. This is the money the offer pays out.
    rewardAmount = models.DecimalField(**MONEY, default=0)
    # Carton price auto-filled from the selected free product (snapshot).
    cartonPrice = models.DecimalField(**MONEY, default=0)
    accrued = models.DecimalField(**MONEY, default=0)
    status = models.CharField(max_length=40)
    # Structured discount so a qualifying sale can be calculated automatically.
    #   None        — no automatic discount (reward text only)
    #   Percentage  — discountValue % off the qualifying gross
    #   Flat        — discountValue flat amount off
    #   BuyXGetY    — every `buyQty` qualifying units grants `getQty` free units
    #                 of `freeSku` (blank freeSku = more of the same product)
    discountType = models.CharField(max_length=20, default="None")
    discountValue = models.DecimalField(**MONEY, default=0)
    buyQty = models.IntegerField(default=0)
    getQty = models.IntegerField(default=0)
    freeSku = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} — {self.name}"


class OfferAccrual(models.Model):
    shop = models.CharField(max_length=200)
    offer = models.CharField(max_length=200)
    # ISO date this accrual record is "as of" — lets accruals be filtered by
    # date range like every other table (previously only payout_last_date
    # existed, which only covers rows that have already been paid out once).
    date = models.CharField(max_length=20, blank=True, default="")
    purchases = models.DecimalField(**MONEY, default=0)
    target = models.DecimalField(**MONEY, default=0)  # sales target for this shop/offer
    accrued = models.DecimalField(**MONEY, default=0)
    status = models.CharField(max_length=40)
    payout_last_date = models.CharField(max_length=20, blank=True, default="")  # ISO date of last payout

    class Meta:
        ordering = ["shop"]

    def __str__(self):
        return f"{self.shop} / {self.offer}"


class Salesman(models.Model):
    id = models.CharField(max_length=40, primary_key=True)  # e.g. SR-01
    name = models.CharField(max_length=200)
    # Optional: a newly added employee may not be assigned an area/territory yet.
    area = models.CharField(max_length=120, blank=True, default="")
    territory = models.CharField(max_length=120, blank=True, default="")
    target = models.DecimalField(**MONEY, default=0)
    achieved = models.DecimalField(**MONEY, default=0)
    shops = models.IntegerField(default=0)
    commission = models.DecimalField(**MONEY, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} — {self.name}"


class Attendance(models.Model):
    """One employee's attendance for one date.

    Statuses are derived from the shift window on CompanySettings rather than
    typed in by hand, so "Late Present" and "Early Out" mean the same thing for
    everybody. `status` still accepts the manual values (Absent / Leave / On
    Field) an admin sets directly.
    """

    # Shift-derived statuses. "Late Present" and "Early Out" are separate axes:
    # someone can arrive late *and* leave early, in which case both flags are
    # set and `status` reports "Late Present" (arrival is the stricter signal).
    STATUS_PRESENT = "Present"
    STATUS_LATE = "Late Present"
    STATUS_EARLY_OUT = "Early Out"

    # `in` / `out` are Python keywords, so stored as check_in / check_out and
    # renamed back to "in" / "out" by the serializer.
    sr_id = models.CharField(max_length=40)  # SR id (not unique across dates)
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=254, blank=True, default="")
    check_in = models.CharField(max_length=20, blank=True, default="")
    check_out = models.CharField(max_length=20, blank=True, default="")
    # Present | Late Present | Early Out | Absent | On Field | Leave
    status = models.CharField(max_length=40)
    visits = models.IntegerField(default=0)
    date = models.CharField(max_length=20, blank=True, default="")
    inLoc = models.CharField(max_length=200, blank=True, default="")
    outLoc = models.CharField(max_length=200, blank=True, default="")
    # Minutes past shiftStart at check-in (0 when on time) and minutes short of
    # shiftEnd at check-out (0 when the full shift was worked). Stored rather
    # than recomputed so a later change to the shift window doesn't silently
    # rewrite history.
    lateMinutes = models.IntegerField(default=0)
    earlyMinutes = models.IntegerField(default=0)

    class Meta:
        ordering = ["sr_id"]

    def __str__(self):
        return f"{self.sr_id} — {self.name} ({self.status})"


class LedgerEntry(models.Model):
    date = models.CharField(max_length=20)
    account = models.CharField(max_length=200)
    debit = models.DecimalField(**MONEY, default=0)
    credit = models.DecimalField(**MONEY, default=0)
    type = models.CharField(max_length=40)  # Income | Asset | Expense | Liability
    ref = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-date", "id"]

    def __str__(self):
        return f"{self.date} — {self.account}"


class Visit(models.Model):
    date = models.CharField(max_length=20, blank=True, default="")  # ISO date string
    time = models.CharField(max_length=20)
    srId = models.CharField(max_length=40, blank=True, default="")
    sr = models.CharField(max_length=200)
    shop = models.CharField(max_length=200)
    outcome = models.CharField(max_length=120)
    note = models.CharField(max_length=400, blank=True, default="")
    followup = models.CharField(max_length=40, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")  # GPS coords

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.sr} @ {self.shop}"


class Payment(models.Model):
    id = models.CharField(max_length=40, primary_key=True)  # e.g. PMT-50001
    invoiceId = models.CharField(max_length=40)
    shop = models.CharField(max_length=200)
    date = models.CharField(max_length=20)
    amount = models.DecimalField(**MONEY, default=0)
    method = models.CharField(max_length=40)  # Cash | Bank | bKash | Cashback
    txn = models.CharField(max_length=80, blank=True, default="")
    note = models.CharField(max_length=400, blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.id


class Payout(models.Model):
    """A reimbursement paid out to a shop against its accrued offer/cashback
    liability. The pending balance per shop is (accrued not yet Paid) minus the
    sum of payouts recorded here; the latest payout date is the shop's
    'Last Payment Date' in the Pending Pay-out view."""

    id = models.CharField(max_length=40, primary_key=True)  # e.g. PO-80001
    shop = models.CharField(max_length=200)
    date = models.CharField(max_length=20)  # ISO date string
    amount = models.DecimalField(**MONEY, default=0)
    method = models.CharField(max_length=40, default="Cash")  # Cash | Bank | bKash | Adjustment
    offer = models.CharField(max_length=200, blank=True, default="")
    note = models.CharField(max_length=400, blank=True, default="")
    payout_last_date = models.CharField(max_length=20, blank=True, default="")  # ISO date string

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.id} — {self.shop}"


class ShopReview(models.Model):
    """A positive/negative review left against a customer (shop/dealer)."""

    shop = models.CharField(max_length=200)  # shop name
    date = models.CharField(max_length=20)  # ISO date string
    sentiment = models.CharField(max_length=20)  # Positive | Negative
    note = models.CharField(max_length=600, blank=True, default="")
    author = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.shop} — {self.sentiment}"


class CashbackTxn(models.Model):
    id = models.CharField(max_length=40, primary_key=True)  # e.g. CBK-70001
    shop = models.CharField(max_length=200)
    date = models.CharField(max_length=20)
    type = models.CharField(max_length=20)  # Earned | Redeemed
    amount = models.DecimalField(**MONEY, default=0)
    offer = models.CharField(max_length=200, blank=True, default="")
    invoiceId = models.CharField(max_length=40, blank=True, default="")
    note = models.CharField(max_length=400, blank=True, default="")
    payout_last_date = models.CharField(max_length=20, blank=True, default="")  # ISO date of last payout
    payout_deadline = models.CharField(max_length=20, blank=True, default="")  # payout must be completed by this date
    payout_status = models.CharField(max_length=20, blank=True, default="")  # Pending | Paid | Overdue

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.id} — {self.shop}"


class Target(models.Model):
    HONORARIUM_TYPE_CHOICES = [
        ("Amount", "Amount"),
        ("Gift", "Gift"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    ]
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=400, blank=True, default="")
    # Which employee this target campaign is assigned to — any HR designation
    # (DSM/ASM/ASE/FSE/...), not only field-sales entries in the separate
    # Salesman table (which most agencies never populate). References
    # core.Employee (the HR directory / login account) directly. Nullable so
    # existing targets created before this field don't break; new ones are
    # required to set it from the frontend dropdown.
    employee = models.ForeignKey(
        "Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="targets"
    )
    # Optional: scopes this campaign to one specific outlet instead of (or in
    # addition to) the employee above — an outlet-wise target rather than a
    # sales-team target.
    shop = models.ForeignKey(
        "Shop", on_delete=models.SET_NULL, null=True, blank=True, related_name="targets"
    )
    target_value = models.DecimalField(max_digits=16, decimal_places=2)
    shop_visit_target = models.IntegerField(default=0)
    honorarium_type = models.CharField(max_length=10, choices=HONORARIUM_TYPE_CHOICES, default="Amount")
    honorarium_value = models.CharField(max_length=200)
    start_date = models.CharField(max_length=20)
    end_date = models.CharField(max_length=20)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Active")

    class Meta:
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name


class DamageRecord(models.Model):
    """A write-off of product stock — damaged, expired, or otherwise lost —
    kept separate from normal sales-driven stock depletion so shrinkage is
    visible and auditable on its own. Decrementing the product's good stock
    when a record is created (and adding it back when the record is edited or
    deleted) is orchestrated client-side in products.tsx, mirroring the way
    sales.tsx handles sales orders, so all stock math lives in one place in
    the frontend."""

    REASON_CHOICES = [
        ("Damaged", "Damaged"),
        ("Expired", "Expired"),
        ("Broken in Transit", "Broken in Transit"),
        ("Quality Issue", "Quality Issue"),
        ("Other", "Other"),
    ]
    id = models.CharField(max_length=40, primary_key=True)  # e.g. DMG-00001
    date = models.CharField(max_length=20)  # ISO date string
    sku = models.CharField(max_length=40)
    productName = models.CharField(max_length=200, blank=True, default="")  # snapshot, survives product edits/deletes
    quantity = models.IntegerField(default=0)
    unit_type = models.CharField(max_length=10, default="PCS")  # PCS | Carton — snapshot from the product
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default="Damaged")
    loss_value = models.DecimalField(**MONEY, default=0)  # quantity × unit price at the time of write-off
    # Total pieces this write-off removed from good stock, snapshotted at entry
    # time. `quantity` is in whatever unit was typed (cartons or pieces), so on
    # its own it can't be reversed once the product's pcs_per_carton changes —
    # this field is what an edit/delete adds back.
    damaged_pcs = models.IntegerField(default=0)
    # Pieces per carton at the time of write-off, kept so the record can still
    # be rendered in cartons + loose pieces after the product is re-packed.
    pcs_per_carton = models.IntegerField(default=1)
    note = models.CharField(max_length=400, blank=True, default="")
    reportedBy = models.CharField(max_length=200, blank=True, default="")
    createdAt = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.id} — {self.sku} x{self.quantity} ({self.reason})"


class StockEntry(models.Model):
    """A restock — cartons or pieces added to a product's good stock. The
    mirror image of DamageRecord: same shape, opposite direction. Kept
    separate from the product's own carton/extra_pcs fields (which an edit can
    also overwrite directly) so there's an auditable log of "who added how
    much, when" — incrementing the product's good stock when a record is
    created, and reversing that on edit/delete, is orchestrated client-side in
    products.tsx exactly like DamageRecord."""

    SOURCE_CHOICES = [
        ("Purchase", "Purchase"),
        ("Return", "Return"),
        ("Transfer In", "Transfer In"),
        ("Correction", "Correction"),
        ("Other", "Other"),
    ]
    id = models.CharField(max_length=40, primary_key=True)  # e.g. STK-00001
    date = models.CharField(max_length=20)  # ISO date string
    sku = models.CharField(max_length=40)
    productName = models.CharField(max_length=200, blank=True, default="")  # snapshot, survives product edits/deletes
    quantity = models.IntegerField(default=0)
    unit_type = models.CharField(max_length=10, default="PCS")  # PCS | Carton — snapshot from the product
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="Purchase")
    # Total pieces this entry added to good stock, snapshotted at entry time —
    # same reasoning as DamageRecord.damaged_pcs: what an edit/delete reverses.
    added_pcs = models.IntegerField(default=0)
    pcs_per_carton = models.IntegerField(default=1)
    note = models.CharField(max_length=400, blank=True, default="")
    addedBy = models.CharField(max_length=200, blank=True, default="")
    createdAt = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "stock entries"

    def __str__(self):
        return f"{self.id} — {self.sku} x{self.quantity} ({self.source})"


# ---------------------------------------------------------------------------
# HR Module — Employee Management
# ---------------------------------------------------------------------------
class EmployeeManager(BaseUserManager):
    """Mirrors Django's default UserManager, but on Employee: an id_no
    (business employee ID) is minted automatically when one isn't supplied,
    and a joining_date defaults to today so `createsuperuser` works without
    prompting for every HR field."""

    use_in_migrations = True

    def _next_id_no(self):
        highest = 0
        for id_no in self.model.objects.values_list("id_no", flat=True):
            digits = "".join(ch for ch in str(id_no) if ch.isdigit())
            if digits:
                highest = max(highest, int(digits))
        return f"EMP-{highest + 1:03d}"

    def _create_employee(self, email, password, **extra):
        if not email:
            raise ValueError("Employees must have an email address")
        email = self.normalize_email(email)
        from datetime import date

        extra.setdefault("id_no", self._next_id_no())
        extra.setdefault("joining_date", date.today())
        employee = self.model(email=email, **extra)
        employee.set_password(password)
        employee.save(using=self._db)
        return employee

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_employee(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("designation", "Manager")
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_employee(email, password, **extra)


class Employee(AbstractBaseUser, PermissionsMixin):
    """Complete employee profile — and the login account itself.

    There is no separate accounts.User table: this model *is*
    settings.AUTH_USER_MODEL. `designation` is both the job title and the
    system access role (see accounts/permissions.py, src/lib/auth.tsx);
    `id_no` is both the business employee ID and the Django primary key.
    """

    DESIGNATION_CHOICES = [
        # "Manager" is the value stored and compared everywhere in code
        # (accounts/permissions.py, this file, the frontend's PERMS/auth.tsx) —
        # only the human-facing label changed to "Super Admin". Renaming the
        # stored value itself would mean migrating every existing employee
        # row and every one of those code comparisons; not worth the churn
        # for a label change. See roleLabel() in the frontend's lib/auth.tsx.
        ("Manager", "Super Admin"),
        ("DSM", "Divisional Sales Manager"),
        ("ASM", "Area Sales Manager"),
        ("ASE", "Area Sales Executive"),
        ("FSE", "Field Sales Executive"),
        ("Support Staff", "Support Staff"),
        ("Administrative", "Administrative"),
        ("Accountant", "Accountant"),
        ("HR", "HR & Admin"),
    ]

    # Primary identification
    id_no = models.CharField(max_length=40, primary_key=True)  # e.g., EMP-001
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)

    # Personal details
    fathers_name = models.CharField(max_length=200, blank=True, default="")
    mothers_name = models.CharField(max_length=200, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    home_district = models.CharField(max_length=120, blank=True, default="")
    permanent_address = models.CharField(max_length=400, blank=True, default="")

    # Professional details
    designation = models.CharField(max_length=50, choices=DESIGNATION_CHOICES, default="FSE")
    # The reporting manager for the sales hierarchy (DSM -> ASM -> ASE/FSE).
    # Self-referential rather than a dedicated Manager model since the
    # manager is just another Employee row. SET_NULL so removing a manager
    # never cascades into deleting their reports.
    reports_to = models.ForeignKey(
        "self", related_name="direct_reports", on_delete=models.SET_NULL, null=True, blank=True
    )
    branch = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, default="Active")  # Active | Inactive
    joining_date = models.DateField()
    salary = models.DecimalField(**MONEY, default=0)

    # HR tracking
    promotion_history_count = models.IntegerField(default=0, editable=False)
    particulars_rewards = models.TextField(blank=True, default="")  # Multi-line text for rewards
    particulars_punishment = models.TextField(blank=True, default="")  # Multi-line text for punishments

    # Login / access (AbstractBaseUser gives password + last_login; PermissionsMixin
    # gives is_superuser + groups + user_permissions)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    objects = EmployeeManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return f"{self.id_no} — {self.name} ({self.designation})"

    @property
    def role(self):
        """Alias so role-based permission code (`request.user.role`) keeps
        working unchanged — designation *is* the system role."""
        return self.designation

    def downline(self):
        """Every employee who reports to this one, directly or transitively
        (DSM -> ASM -> ASE -> FSE and so on). Iterative BFS rather than a
        recursive queryset so a stray cycle can't hang the request."""
        result = []
        seen = {self.id_no}
        frontier = list(self.direct_reports.all())
        while frontier:
            emp = frontier.pop()
            if emp.id_no in seen:
                continue
            seen.add(emp.id_no)
            result.append(emp)
            frontier.extend(emp.direct_reports.all())
        return result

    @property
    def age(self):
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    @property
    def years_of_service(self):
        """Calculate years since joining."""
        from datetime import date
        today = date.today()
        return today.year - self.joining_date.year - ((today.month, today.day) < (self.joining_date.month, self.joining_date.day))


class PromotionHistory(models.Model):
    """Track employee promotions and designation changes."""

    PROMOTION_TYPE_CHOICES = [
        ("Promotion", "Promotion"),
        ("Demotion", "Demotion"),
        ("Transfer", "Transfer"),
        ("Lateral Move", "Lateral Move"),
    ]

    id = models.CharField(max_length=40, primary_key=True)  # e.g., PROMO-001
    employee = models.ForeignKey(Employee, related_name="promotions", on_delete=models.CASCADE)
    promotion_date = models.DateField()
    promotion_type = models.CharField(max_length=20, choices=PROMOTION_TYPE_CHOICES, default="Promotion")
    from_designation = models.CharField(max_length=50)  # Previous designation (snapshot)
    to_designation = models.CharField(max_length=50)  # New designation
    from_area = models.CharField(max_length=120, blank=True, default="")  # Previous area (if applicable)
    to_area = models.CharField(max_length=120, blank=True, default="")  # New area (if applicable)
    from_salary = models.DecimalField(**MONEY, default=0, blank=True)  # Previous salary (snapshot)
    to_salary = models.DecimalField(**MONEY, default=0, blank=True)  # New salary
    reason = models.CharField(max_length=200, blank=True, default="")  # Reason for promotion
    notes = models.TextField(blank=True, default="")  # Additional notes
    approved_by = models.CharField(max_length=200, blank=True, default="")  # Approver name
    approved_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-promotion_date", "-id"]
        verbose_name = "Promotion History"
        verbose_name_plural = "Promotion Histories"

    def __str__(self):
        return f"{self.id} — {self.employee.name}: {self.from_designation} → {self.to_designation}"


class EmployeeReward(models.Model):
    """Track specific rewards/awards given to employees."""

    id = models.CharField(max_length=40, primary_key=True)  # e.g., REWARD-001
    employee = models.ForeignKey(Employee, related_name="rewards", on_delete=models.CASCADE)
    date = models.DateField()
    reward_type = models.CharField(max_length=100)  # e.g., "Excellence Award", "Performance Bonus"
    description = models.CharField(max_length=400)  # Details of the reward
    amount = models.DecimalField(**MONEY, default=0, blank=True)  # Monetary reward amount if applicable
    issued_by = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.id} — {self.employee.name}: {self.reward_type}"


class EmployeePunishment(models.Model):
    """Track disciplinary actions/punishments."""

    SEVERITY_CHOICES = [
        ("Warning", "Warning"),
        ("Suspension", "Suspension"),
        ("Fine", "Fine"),
        ("Termination", "Termination"),
    ]

    id = models.CharField(max_length=40, primary_key=True)  # e.g., PUNISH-001
    employee = models.ForeignKey(Employee, related_name="punishments", on_delete=models.CASCADE)
    date = models.DateField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="Warning")
    offense = models.CharField(max_length=200)  # Nature of the offense
    description = models.TextField()  # Detailed description
    action_taken = models.CharField(max_length=400)  # Action taken
    duration_days = models.IntegerField(default=0, blank=True)  # For suspensions (number of days)
    fine_amount = models.DecimalField(**MONEY, default=0, blank=True)  # For fines
    issued_by = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.id} — {self.employee.name}: {self.severity}"
