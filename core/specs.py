"""
Column specs for the bulk import/export templates.

Kept apart from importexport.py so the mechanics (how a workbook is built) stay
separate from the business shape (which columns each model has). Adding a new
importable collection means adding a Spec here and three lines on its viewset.
"""
from .importexport import Column, Spec
from .models import (
    Area,
    Brand,
    Product,
    ProductCategory,
    ProductSegment,
    Salesman,
    Shop,
    ShopCategory,
    Territory,
    Unit,
)


def _territory_names():
    return lambda: list(Territory.objects.values_list("name", flat=True)[:60])


def _region_names():
    from .models import Region

    return lambda: list(Region.objects.filter(active=True).values_list("name", flat=True)[:60])


def _active_names(model):
    """Dropdown options for the template, from the Settings master lists."""
    return lambda: list(model.objects.filter(active=True).values_list("name", flat=True)[:60])


def _salesman_names():
    return lambda: list(Salesman.objects.values_list("name", flat=True)[:60])


# ============================================================================
# PRODUCTS
# ============================================================================
PRODUCT_SPEC = Spec(
    name="Products & Stock",
    filename="products",
    id_field="sku",
    columns=[
        Column(
            key="sku",
            header="SKU",
            required=True,
            help="Unique product code. Leave blank for new products (auto-generated).",
            sample="PROD-001",
        ),
        Column(
            key="name",
            header="Product Name",
            required=True,
            help="Full name of the product.",
            sample="Coca Cola 1.5L",
        ),
        Column(
            key="segment",
            header="Product Segment",
            choices=_active_names(ProductSegment),
            help="Product segment from Settings.",
            sample="Personal Hygiene",
        ),
        Column(
            key="category",
            header="Category",
            required=True,
            choices=_active_names(ProductCategory),
            help="Product category from Settings.",
            sample="Beverages",
        ),
        Column(
            key="brand",
            header="Brand",
            choices=_active_names(Brand),
            help="Brand name from Settings.",
            sample="Coca Cola",
        ),
        Column(
            key="unit_type",
            header="Unit Type",
            choices=lambda: ["PCS", "Carton", "Box", "Pack"],
            help="Unit of measurement (PCS, Carton, Box, Pack).",
            sample="PCS",
        ),
        Column(
            key="unit",
            header="Unit",
            choices=_active_names(Unit),
            help="Unit name from Settings.",
            sample="Piece",
        ),
        Column(
            key="price",
            header="Price (৳)",
            kind="number",
            required=True,
            help="Selling price in taka.",
            sample="150",
        ),
        Column(
            key="cartonPrice",
            header="Carton Price (৳)",
            kind="number",
            help="Price per carton in taka.",
            sample="1500",
        ),
        Column(
            key="piecePrice",
            header="Piece Price (৳)",
            kind="number",
            help="Price per piece in taka.",
            sample="100",
        ),
        Column(
            key="stock",
            header="Current Stock",
            kind="int",
            help="Current quantity in stock.",
            sample="100",
        ),
        Column(
            key="cartons",
            header="Cartons",
            kind="int",
            help="Number of cartons in stock.",
            sample="10",
        ),
        Column(
            key="pieces",
            header="Pieces",
            kind="int",
            help="Number of individual pieces in stock.",
            sample="50",
        ),
        Column(
            key="pcs_per_carton",
            header="Pieces Per Carton",
            kind="int",
            help="How many pieces fit in one carton.",
            sample="12",
        ),
        Column(
            key="expiry",
            header="Expiry Date",
            kind="date",
            help="Product expiry date (YYYY-MM-DD).",
            sample="2026-12-31",
        ),
    ],
)


# ============================================================================
# OFFERS & DISCOUNTS
# ============================================================================
OFFER_SPEC = Spec(
    name="Offers & Discounts",
    filename="offers",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Offer ID",
            help="Leave blank for new offers (auto-generated).",
            sample="",
        ),
        Column(
            key="name",
            header="Offer Name",
            required=True,
            help="Name of the promotional offer.",
            sample="Summer Sale 2026",
        ),
        Column(
            key="type",
            header="Offer Type",
            choices=lambda: ["Discount", "Cashback", "BOGO", "Bundle"],
            help="Type of offer.",
            sample="Discount",
        ),
        Column(
            key="start",
            header="Start Date",
            required=True,
            help="Date when offer starts.",
            sample="2026-06-01",
        ),
        Column(
            key="end",
            header="End Date",
            required=True,
            help="Date when offer ends.",
            sample="2026-06-30",
        ),
        Column(
            key="minQty",
            header="Min Quantity",
            kind="int",
            help="Minimum quantity required.",
            sample="10",
        ),
        Column(
            key="minValue",
            header="Min Value (৳)",
            kind="number",
            help="Minimum purchase amount required.",
            sample="1000",
        ),
        Column(
            key="reward",
            header="Reward Type",
            help="Type of reward/discount.",
            sample="Cashback",
        ),
        Column(
            key="rewardAmount",
            header="Reward Amount (৳)",
            kind="number",
            help="Amount of reward or discount.",
            sample="500",
        ),
        Column(
            key="status",
            header="Status",
            choices=lambda: ["Active", "Pending", "Closed"],
            help="Current status of the offer.",
            sample="Active",
        ),
    ],
)


# ============================================================================
# SALES ORDERS
# ============================================================================
SALES_ORDER_SPEC = Spec(
    name="Sales Orders",
    filename="sales",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Invoice ID",
            help="Leave blank for new orders (auto-generated).",
            sample="",
        ),
        Column(
            key="date",
            header="Date",
            kind="date",
            required=True,
            help="Date of sale (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
        Column(
            key="shop",
            header="Outlet Code",
            required=True,
            help="Code of the outlet/shop.",
            sample="SH-5001",
        ),
        Column(
            key="sr",
            header="Sales Officer",
            choices=_salesman_names(),
            help="Name of the sales officer.",
            sample="Karim Uddin",
        ),
        Column(
            key="gross",
            header="Gross Amount (৳)",
            kind="number",
            help="Total before discount.",
            sample="5000",
        ),
        Column(
            key="discount",
            header="Discount (৳)",
            kind="number",
            help="Discount amount.",
            sample="500",
        ),
        Column(
            key="vatPercent",
            header="VAT (%)",
            kind="number",
            help="VAT percentage applied on the gross amount.",
            sample="15",
        ),
        Column(
            key="vat",
            header="VAT Amount (৳)",
            kind="number",
            help="VAT amount (gross x VAT%).",
            sample="750",
        ),
        Column(
            key="stage",
            header="Stage",
            choices=lambda: ["Draft", "Confirmed", "Delivered"],
            help="Order stage.",
            sample="Delivered",
        ),
        Column(
            key="deliveredDate",
            header="Delivery Date",
            kind="date",
            help="Date when order was delivered (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
    ],
)


# ============================================================================
# ATTENDANCE
# ============================================================================
ATTENDANCE_SPEC = Spec(
    name="Attendance Records",
    filename="attendance",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Attendance ID",
            help="Leave blank for new records (auto-generated).",
            sample="",
        ),
        Column(
            key="sr_id",
            header="Employee ID",
            required=True,
            help="Employee ID (e.g., SR-01).",
            sample="SR-01",
        ),
        Column(
            key="name",
            header="Employee Name",
            required=True,
            help="Full name of employee.",
            sample="Karim Uddin",
        ),
        Column(
            key="date",
            header="Date",
            kind="date",
            required=True,
            help="Attendance date (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
        Column(
            key="check_in",
            header="Check In Time",
            help="Check in time (HH:MM format).",
            sample="09:00",
        ),
        Column(
            key="check_out",
            header="Check Out Time",
            help="Check out time (HH:MM format).",
            sample="17:00",
        ),
        Column(
            key="status",
            header="Status",
            choices=lambda: ["Present", "Late Present", "Early Out", "Absent", "Leave"],
            help="Attendance status.",
            sample="Present",
        ),
        Column(
            key="visits",
            header="Visits",
            kind="int",
            help="Number of outlet visits.",
            sample="5",
        ),
    ],
)


# ============================================================================
# PAYMENTS
# ============================================================================
PAYMENT_SPEC = Spec(
    name="Payments Received",
    filename="payments",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Payment ID",
            help="Leave blank for new payments (auto-generated).",
            sample="",
        ),
        Column(
            key="date",
            header="Date",
            kind="date",
            required=True,
            help="Payment date (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
        Column(
            key="shop",
            header="Outlet Code",
            required=True,
            help="Code of outlet making payment.",
            sample="SH-5001",
        ),
        Column(
            key="invoiceId",
            header="Invoice ID",
            help="Related invoice ID.",
            sample="INV-001",
        ),
        Column(
            key="amount",
            header="Amount (৳)",
            kind="number",
            required=True,
            help="Payment amount in taka.",
            sample="2000",
        ),
        Column(
            key="method",
            header="Method",
            choices=lambda: ["Cash", "Bank Transfer", "bKash", "Nagad", "Rocket"],
            help="Payment method.",
            sample="Cash",
        ),
        Column(
            key="txn",
            header="Transaction Reference",
            help="Transaction reference or check number.",
            sample="TXN-123456",
        ),
        Column(
            key="note",
            header="Note",
            help="Additional notes.",
            sample="",
        ),
    ],
)


# ============================================================================
# VISITS
# ============================================================================
VISIT_SPEC = Spec(
    name="Outlet Visits",
    filename="visits",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Visit ID",
            help="Leave blank for new visits (auto-generated).",
            sample="",
        ),
        Column(
            key="date",
            header="Date",
            kind="date",
            required=True,
            help="Visit date (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
        Column(
            key="sr",
            header="Sales Officer",
            choices=_salesman_names(),
            help="Sales officer name.",
            sample="Karim Uddin",
        ),
        Column(
            key="shop",
            header="Outlet Code",
            required=True,
            help="Outlet code visited.",
            sample="SH-5001",
        ),
        Column(
            key="time",
            header="Time",
            help="Visit time (HH:MM format).",
            sample="10:30",
        ),
        Column(
            key="outcome",
            header="Outcome",
            choices=lambda: ["Sale", "Follow-up", "No Sale", "Closed", "Not Found"],
            help="Visit outcome.",
            sample="Sale",
        ),
        Column(
            key="note",
            header="Notes",
            help="Additional notes about the visit.",
            sample="Discussed new product line",
        ),
        Column(
            key="followup",
            header="Follow-up Required",
            choices=lambda: ["Yes", "No"],
            help="Is follow-up required?",
            sample="No",
        ),
        Column(
            key="location",
            header="Location",
            help="Visit location coordinates or address.",
            sample="",
        ),
    ],
)


# ============================================================================
# CASHBACK TRANSACTIONS
# ============================================================================
CASHBACK_SPEC = Spec(
    name="Cashback Transactions",
    filename="cashback",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Transaction ID",
            help="Leave blank for new transactions (auto-generated).",
            sample="",
        ),
        Column(
            key="date",
            header="Date",
            kind="date",
            required=True,
            help="Transaction date (YYYY-MM-DD).",
            sample="2026-06-15",
        ),
        Column(
            key="shop",
            header="Outlet Code",
            required=True,
            help="Outlet code.",
            sample="SH-5001",
        ),
        Column(
            key="type",
            header="Type",
            choices=lambda: ["Earned", "Redeemed"],
            help="Transaction type.",
            sample="Earned",
        ),
        Column(
            key="amount",
            header="Amount (৳)",
            kind="number",
            required=True,
            help="Cashback amount in taka.",
            sample="500",
        ),
        Column(
            key="offer",
            header="Related Offer",
            help="Offer code or name.",
            sample="SUMMER2026",
        ),
        Column(
            key="invoiceId",
            header="Invoice ID",
            help="Related invoice or transaction ID.",
            sample="INV-001",
        ),
        Column(
            key="note",
            header="Note",
            help="Additional notes.",
            sample="",
        ),
        Column(
            key="payout_last_date",
            header="Payout Last Date",
            help="Last payout date.",
            sample="",
        ),
        Column(
            key="payout_deadline",
            header="Payout Deadline",
            help="Payout deadline date.",
            sample="",
        ),
        Column(
            key="payout_status",
            header="Payout Status",
            choices=lambda: ["Pending", "Completed", "Failed"],
            help="Payout status.",
            sample="Pending",
        ),
    ],
)


# ============================================================================
# TARGETS
# ============================================================================
TARGET_SPEC = Spec(
    name="Sales Targets",
    filename="targets",
    id_field="id",
    columns=[
        Column(
            key="id",
            header="Target ID",
            help="Leave blank for new targets (auto-generated).",
            sample="",
        ),
        Column(
            key="name",
            header="Target Name",
            required=True,
            help="Name of the target campaign.",
            sample="Q3 Sales Target",
        ),
        Column(
            key="description",
            header="Description",
            help="Details about the target campaign.",
            sample="Summer promotion target",
        ),
        Column(
            key="target_value",
            header="Target Amount (৳)",
            kind="number",
            required=True,
            help="Sales target in taka.",
            sample="500000",
        ),
        Column(
            key="shop_visit_target",
            header="Shop Visit Target",
            kind="int",
            help="Target number of shop visits.",
            sample="100",
        ),
        Column(
            key="start_date",
            header="Start Date",
            required=True,
            help="Start date (YYYY-MM-DD).",
            sample="2026-07-01",
        ),
        Column(
            key="end_date",
            header="End Date",
            required=True,
            help="End date (YYYY-MM-DD).",
            sample="2026-09-30",
        ),
        Column(
            key="status",
            header="Status",
            choices=lambda: ["Active", "Inactive"],
            help="Status of the target.",
            sample="Active",
        ),
        Column(
            key="honorarium_type",
            header="Honorarium Type",
            choices=lambda: ["Amount", "Gift"],
            help="Type of incentive.",
            sample="Amount",
        ),
        Column(
            key="honorarium_value",
            header="Honorarium Value",
            help="Amount or value of incentive (as text).",
            sample="50000",
        ),
    ],
)


# ============================================================================
# EMPLOYEES (HR)
# ============================================================================
EMPLOYEE_SPEC = Spec(
    name="Employees",
    filename="employees",
    id_field="id_no",
    columns=[
        Column(
            key="id_no",
            header="Employee ID",
            required=True,
            help="Unique employee ID (e.g., EMP-001).",
            sample="EMP-001",
        ),
        Column(
            key="name",
            header="Full Name",
            required=True,
            help="Full name of employee.",
            sample="Ahmed Hassan",
        ),
        Column(
            key="email",
            header="Email",
            required=True,
            help="Email address.",
            sample="ahmed@company.com",
        ),
        Column(
            key="fathers_name",
            header="Father's Name",
            help="Father's full name.",
            sample="Hassan Ahmed",
        ),
        Column(
            key="mothers_name",
            header="Mother's Name",
            help="Mother's full name.",
            sample="Fatima Khan",
        ),
        Column(
            key="designation",
            header="Designation",
            choices=lambda: ["Manager", "DSM", "ASM", "ASE", "FSE", "Support Staff", "Administrative", "HR"],
            required=True,
            help="Job designation.",
            sample="ASM",
        ),
        Column(
            key="date_of_birth",
            header="Date of Birth",
            kind="date",
            help="DOB in YYYY-MM-DD format.",
            sample="1990-05-15",
        ),
        Column(
            key="joining_date",
            header="Joining Date",
            kind="date",
            required=True,
            help="Employment start date (YYYY-MM-DD).",
            sample="2020-01-15",
        ),
        Column(
            key="salary",
            header="Salary (৳)",
            kind="number",
            required=True,
            help="Monthly salary in taka.",
            sample="50000",
        ),
        Column(
            key="home_district",
            header="Home District",
            help="District of residence.",
            sample="Dhaka",
        ),
        Column(
            key="permanent_address",
            header="Permanent Address",
            help="Full permanent address.",
            sample="House 42, Road 11, Banani, Dhaka",
        ),
        Column(
            key="branch",
            header="Branch",
            help="Office/branch the employee is based at.",
            sample="HQ",
        ),
        Column(
            key="status",
            header="Status",
            choices=lambda: ["Active", "Inactive"],
            help="Employment status.",
            sample="Active",
        ),
    ],
)


# ============================================================================
# SHOPS / OUTLETS
# ============================================================================
SHOP_SPEC = Spec(
    name="Outlet, Wholesalers & Dealer",
    filename="shops",
    id_field="code",
    columns=[
        Column(key="code", header="Outlet Code", help="Leave blank for new outlets — auto-generated.", sample=""),
        Column(key="name", header="Outlet Name", required=True, help="Trading name.", sample="Rahman Store"),
        Column(key="category", header="Category", required=True, choices=_active_names(ShopCategory), sample="Retail"),
        Column(key="area", header="Area", required=True, choices=_active_names(Area), sample="Dhaka North"),
        Column(key="territory", header="Territory", required=True, choices=_active_names(Territory), sample="Banani"),
        Column(key="zone", header="Division", help="Optional top-level geography.", sample="Dhaka"),
        Column(key="district", header="District", help="Optional district.", sample="Dhaka"),
        Column(key="thana", header="Thana", help="Optional thana / upazila.", sample="Gulshan"),
        Column(key="owner", header="Owner Name", required=True, help="Account owner.", sample="Abdul Rahman"),
        Column(key="phone", header="Owner Number", help="Contact number.", sample="01712345678"),
        Column(key="address", header="Address", help="Street address.", sample="House 42, Road 11, Banani"),
        Column(key="credit", header="Credit Limit (৳)", kind="number", help="Max credit allowed.", sample="50000"),
        Column(key="sales30d", header="MTD Sales (৳)", kind="number", sample="0"),
        Column(key="srName", header="Sales Officer", choices=_salesman_names(), sample="Karim Uddin"),
        Column(key="srEmail", header="Sales Officer Email", sample="karim@example.com"),
        Column(key="dealer_id", header="Dealer Code", kind="fk", help="Code of the dealer this outlet trades under (Dealers page).", sample="DLR-0001"),
    ],
)

# ============================================================================
# DEALERS
# ============================================================================
def _salesman_names_as_ids():
    return lambda: list(Salesman.objects.values_list("id", flat=True)[:60])


DEALER_SPEC = Spec(
    name="Dealers",
    filename="dealers",
    id_field="code",
    columns=[
        Column(key="code", header="Dealer Code", help="Leave blank for new dealers — auto-generated.", sample=""),
        Column(key="name", header="Dealer Name", required=True, help="Trading name of the dealer.", sample="Rahman Distribution"),
        Column(key="region", header="Region", choices=_region_names(), help="Region from Settings.", sample="Dhaka"),
        Column(key="area", header="Area", required=True, choices=_active_names(Area), help="Area from Settings.", sample="Dhaka North"),
        Column(key="territory", header="Territory", required=True, choices=_territory_names(), help="Territory from Settings.", sample="Uttara"),
        Column(key="ase_id", header="ASE Code", kind="fk", choices=_salesman_names_as_ids(), help="ASE's Salesman/Employee ID (e.g. SR-01). Leave blank if unassigned.", sample="SR-01"),
        Column(key="contact_number", header="Contact Number", help="Dealer's contact phone number.", sample="01712345678"),
        Column(key="address", header="Address", help="Dealer's address.", sample="House 42, Road 11, Uttara"),
    ],
)


# ============================================================================
# SALESMEN / SALES OFFICERS
# ============================================================================
SALESMAN_SPEC = Spec(
    name="Sales Officers",
    filename="salesmen",
    id_field="id",
    columns=[
        Column(key="id", header="Employee ID", help="Leave blank for auto-generated SR-## IDs.", sample=""),
        Column(key="name", header="Name", required=True, help="Full name.", sample="Karim Uddin"),
        Column(key="area", header="Area", choices=_active_names(Area), sample="Dhaka North"),
        Column(key="territory", header="Territory", choices=_active_names(Territory), sample="Banani"),
        Column(key="target", header="Target (৳)", kind="number", help="Sales target.", sample="0"),
        Column(key="achieved", header="Achieved (৳)", kind="number", sample="0"),
        Column(key="shops", header="Outlets Assigned", kind="int", sample="0"),
        Column(key="commission", header="Commission (৳)", kind="number", sample="0"),
    ],
)


# ============================================================================
# MASTER SPECS REGISTRY
# ============================================================================
SPECS = {
    "products": PRODUCT_SPEC,
    "offers": OFFER_SPEC,
    "sales": SALES_ORDER_SPEC,
    "attendance": ATTENDANCE_SPEC,
    "payments": PAYMENT_SPEC,
    "visits": VISIT_SPEC,
    "cashback": CASHBACK_SPEC,
    "targets": TARGET_SPEC,
    "employees": EMPLOYEE_SPEC,
    "shops": SHOP_SPEC,
    "salesmen": SALESMAN_SPEC,
    "dealers": DEALER_SPEC,
}


# ============================================================================
# ID GENERATION FUNCTIONS
# ============================================================================
def next_shop_code() -> str:
    """SH-5001, SH-5002 …"""
    from .models import Shop

    highest = 5000
    for code in Shop.objects.values_list("code", flat=True):
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"SH-{highest + 1}"


def next_dealer_code() -> str:
    """DLR-0001, DLR-0002 …"""
    from .models import Dealer

    highest = 0
    for code in Dealer.objects.values_list("code", flat=True):
        digits = "".join(ch for ch in str(code) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"DLR-{highest + 1:04d}"


def next_salesman_id() -> str:
    """SR-01, SR-02 …"""
    from .models import Salesman

    highest = 0
    for pk in Salesman.objects.values_list("id", flat=True):
        digits = "".join(ch for ch in str(pk) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"SR-{highest + 1:02d}"


def next_employee_id() -> str:
    """EMP-001, EMP-002 …"""
    from .models import Employee

    highest = 0
    for id_no in Employee.objects.values_list("id_no", flat=True):
        digits = "".join(ch for ch in str(id_no) if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"EMP-{highest + 1:03d}"
