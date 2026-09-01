"""
Seed the database with the same demo data the React frontend ships in
src/lib/mock.ts, plus the login/demo user accounts from src/lib/auth.tsx.

    python manage.py seed_data          # insert (skips if data already present)
    python manage.py seed_data --flush  # wipe app tables first, then insert

All seeded user accounts use the password "demo123".
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Area,
    Attendance,
    Brand,
    CashbackTxn,
    CompanySettings,
    LedgerEntry,
    Offer,
    OfferAccrual,
    Payment,
    Product,
    ProductCategory,
    SalesOrder,
    Salesman,
    Shop,
    ShopCategory,
    Territory,
    Unit,
    Visit,
)

# Area -> (zone, territories). Mirrors the AREAS/TERRITORIES constants that were
# hardcoded in shops.tsx and targets.tsx.
AREAS_AND_TERRITORIES = [
    ("Dhaka North", "Dhaka", ["Uttara", "Mirpur", "Banani", "Gulshan"]),
    ("Dhaka South", "Dhaka", ["Dhanmondi", "Motijheel", "Old Dhaka"]),
    ("Chattogram", "Chattogram", ["Agrabad", "Halishahar", "Pahartali"]),
    ("Sylhet", "Sylhet", ["Zindabazar", "Ambarkhana"]),
    ("Rajshahi", "Rajshahi", ["Boalia", "Shaheb Bazar"]),
    ("Khulna", "Khulna", ["Khulna Sadar", "Sonadanga"]),
]

User = get_user_model()
DEMO_PASSWORD = "demo123"

# --- Users --------------------------------------------------------------
# Login accounts (from auth.tsx DEMO_USERS) + management accounts (mock.ts users).
USERS = [
    # email, name, role, branch, status, is_admin
    # Role values match Employee.designation (core/models.py) — Manager, DSM,
    # ASM, ASE, SE, Support Staff, Administrative are the only valid roles now.
    ("admin@amc.com", "Ahsan Habib", "Manager", "HQ", "Active", True),
    ("manager@amc.com", "Nazmul Karim", "DSM", "HQ", "Active", False),
    ("area@amc.com", "Rashed Khan", "ASM", "Dhaka North", "Active", False),
    ("sr@amc.com", "Imran Hossain", "SE", "Uttara", "Active", False),
    ("warehouse@amc.com", "Yusuf Ali", "Support Staff", "Tejgaon WH", "Active", False),
    ("accounts@amc.com", "Mahbub Hasan", "Administrative", "HQ", "Active", False),
    ("ahsan@amc.com", "Ahsan Habib", "Manager", "HQ", "Active", True),
    ("nazmul@amc.com", "Nazmul Karim", "DSM", "HQ", "Active", False),
    ("rashed@amc.com", "Rashed Khan", "ASM", "Dhaka North", "Active", False),
    ("shahid@amc.com", "Shahid Alam", "ASE", "Uttara", "Active", False),
    ("imran@amc.com", "Imran Hossain", "SE", "Uttara", "Active", False),
    ("yusuf@amc.com", "Yusuf Ali", "Support Staff", "Tejgaon WH", "Active", False),
    ("mahbub@amc.com", "Mahbub Hasan", "Administrative", "HQ", "Active", False),
]

PRODUCTS = [
    ("AMC-FRZ-001", "Frozen Delight 500g", "Frozen", "AMC Foods", "Box", 320, 1240, 300, "2026-04-12"),
    ("AMC-BEV-014", "Citrus Burst 1L", "Beverage", "Refresho", "Carton", 180, 860, 400, "2026-09-30"),
    ("AMC-SNK-022", "Crispy Wave Chips", "Snacks", "Crunchy", "PCS", 25, 12400, 5000, "2026-02-18"),
    ("AMC-DRY-007", "Premium Basmati 5kg", "Grocery", "Goldenfield", "Bag", 720, 410, 200, "2027-01-05"),
    ("AMC-DRY-031", "Mustard Oil 1L", "Grocery", "Goldenfield", "PCS", 290, 980, 300, "2026-11-20"),
    ("AMC-BEV-021", "Mineral Water 1.5L", "Beverage", "Refresho", "Carton", 30, 5600, 1000, "2027-03-01"),
    ("AMC-SNK-040", "Honey Nut Bar", "Snacks", "Crunchy", "Box", 480, 220, 250, "2026-05-10"),
    ("AMC-FRZ-009", "Chicken Nuggets 1kg", "Frozen", "AMC Foods", "PCS", 410, 540, 150, "2026-07-22"),
    ("AMC-DAI-002", "Full Cream Milk 1L", "Dairy", "AMC Foods", "Carton", 95, 180, 500, "2026-07-18"),
    ("AMC-DAI-011", "Butter 200g", "Dairy", "AMC Foods", "PCS", 210, 640, 200, "2026-08-05"),
    ("AMC-PC-003", "Herbal Hand Wash 250ml", "Personal Care", "PureCare", "PCS", 140, 1420, 400, "2027-06-30"),
    ("AMC-PC-018", "Mint Toothpaste 100g", "Personal Care", "PureCare", "PCS", 90, 0, 300, "2026-12-01"),
    ("AMC-SNK-055", "Choco Cookies 300g", "Snacks", "Crunchy", "Box", 160, 340, 400, "2026-07-27"),
    ("AMC-DRY-045", "Red Lentil 1kg", "Grocery", "Goldenfield", "Bag", 175, 2200, 600, "2027-02-14"),
]

SHOPS = [
    ("SH-1042", "Rahman Grocers", "Large Shop", "Dhaka North", "Uttara", "Dhaka", "Dhaka", "Uttara", "Md. Rahman", "+880 1711-204050", "Sector 7, Uttara, Dhaka North", 80000, 12400, 245000, "sr@amc.com", "Imran Hossain"),
    ("SH-1108", "City Mart", "Premium Shop", "Dhaka South", "Dhanmondi", "Dhaka", "Dhaka", "Dhanmondi", "Sajib Ahmed", "+880 1722-118899", "Road 27, Dhanmondi, Dhaka South", 200000, 56000, 612000, "area@amc.com", "Rashed Khan"),
    ("SH-2031", "Karim Stores", "Medium Shop", "Chattogram", "Agrabad", "Chattogram", "Chattogram", "Agrabad", "A. Karim", "+880 1733-560071", "Agrabad C/A, Chattogram", 40000, 0, 88000, "sr@amc.com", "Imran Hossain"),
    ("SH-2107", "Sea Breeze Super", "Distributor", "Chattogram", "Halishahar", "Chattogram", "Chattogram", "Halishahar", "Iqbal Hossain", "+880 1755-810023", "Block L, Halishahar, Chattogram", 500000, 142000, 1240000, "area@amc.com", "Rashed Khan"),
    ("SH-3009", "Hilltop Bazaar", "Small Shop", "Sylhet", "Zindabazar", "Sylhet", "Sylhet", "Zindabazar", "Nasir Uddin", "+880 1766-330912", "Zindabazar, Sylhet", 15000, 4200, 32000, "sr@amc.com", "Imran Hossain"),
    ("SH-1201", "Green Valley Mart", "Large Shop", "Dhaka North", "Mirpur", "Dhaka", "Dhaka", "Mirpur", "Salma Begum", "+880 1788-447755", "Mirpur 10, Dhaka North", 100000, 22000, 318000, "sr@amc.com", "Imran Hossain"),
    ("SH-4014", "Padma Trading", "Super Distributor", "Rajshahi", "Boalia", "Rajshahi", "Rajshahi", "Boalia", "Touhid Khan", "+880 1799-220088", "Boalia, Rajshahi", 800000, 210000, 1860000, "area@amc.com", "Rashed Khan"),
    ("SH-1330", "New Market Traders", "Medium Shop", "Dhaka North", "Mirpur", "Dhaka", "Dhaka", "Mirpur", "Faruk Ahmed", "+880 1712-668090", "Mirpur 1, Dhaka North", 60000, 8600, 128000, "sr@amc.com", "Imran Hossain"),
    ("SH-2210", "Coastal Distributors", "Distributor", "Chattogram", "Halishahar", "Chattogram", "Chattogram", "Halishahar", "Nurul Alam", "+880 1815-330077", "Port Connecting Rd, Chattogram", 450000, 96000, 980000, "area@amc.com", "Rashed Khan"),
    ("SH-5001", "Jessore Wholesale", "Distributor", "Khulna", "Khulna Sadar", "Khulna", "Jashore", "Boro Bazar", "Habibur Rahman", "+880 1911-540032", "Boro Bazar, Khulna", 350000, 41000, 720000, "area@amc.com", "Rashed Khan"),
    ("SH-1450", "Banani Fresh", "Premium Shop", "Dhaka South", "Dhanmondi", "Dhaka", "Dhaka", "Banani", "Nadia Islam", "+880 1677-889001", "Road 11, Banani, Dhaka South", 150000, 0, 402000, "area@amc.com", "Rashed Khan"),
    ("SH-3120", "Tea Garden Mart", "Small Shop", "Sylhet", "Zindabazar", "Sylhet", "Sylhet", "Ambarkhana", "Rezaul Karim", "+880 1744-120654", "Ambarkhana, Sylhet", 20000, 6800, 46000, "sr@amc.com", "Imran Hossain"),
]

# id, date, shop, sr, srEmail, items, amount, payment, status, bkashTxn, offer
SALES = [
    ("INV-24061", "2026-06-23", "Rahman Grocers", "Imran Hossain", "sr@amc.com", 12, 28400, "Cash", "Paid", "", ""),
    ("INV-24062", "2026-06-23", "City Mart", "Rashed Khan", "area@amc.com", 28, 96200, "Credit", "Due", "", "Eid Festival Cashback"),
    ("INV-24063", "2026-06-23", "Karim Stores", "Imran Hossain", "sr@amc.com", 6, 14800, "bKash", "Paid", "BKS9F2QX10", ""),
    ("INV-24064", "2026-06-23", "Sea Breeze Super", "Rashed Khan", "area@amc.com", 54, 218400, "Credit", "Partial", "", "Turnover Champion Q2"),
    ("INV-24066", "2026-06-22", "Green Valley Mart", "Imran Hossain", "sr@amc.com", 18, 46800, "Cash", "Paid", "", ""),
    ("INV-24067", "2026-06-22", "Hilltop Bazaar", "Imran Hossain", "sr@amc.com", 4, 9200, "Cash", "Paid", "", ""),
    ("INV-24068", "2026-07-03", "New Market Traders", "Imran Hossain", "sr@amc.com", 9, 18600, "Cash", "Paid", "", ""),
    ("INV-24069", "2026-07-03", "Coastal Distributors", "Rashed Khan", "area@amc.com", 40, 164000, "Credit", "Due", "", "Turnover Champion Q2"),
    ("INV-24070", "2026-07-03", "Banani Fresh", "Rashed Khan", "area@amc.com", 22, 78400, "bKash", "Paid", "BKS7H1MP44", ""),
    ("INV-24071", "2026-07-02", "Rahman Grocers", "Imran Hossain", "sr@amc.com", 15, 33200, "Cash", "Paid", "", ""),
    ("INV-24072", "2026-07-02", "Sea Breeze Super", "Rashed Khan", "area@amc.com", 60, 246000, "Credit", "Partial", "", "Turnover Champion Q2"),
    ("INV-24073", "2026-07-02", "Jessore Wholesale", "Rashed Khan", "area@amc.com", 34, 118000, "Credit", "Due", "", ""),
    ("INV-24074", "2026-07-01", "City Mart", "Rashed Khan", "area@amc.com", 26, 91500, "bKash", "Paid", "BKS3K9DZ21", "Eid Festival Cashback"),
    ("INV-24075", "2026-07-01", "Green Valley Mart", "Imran Hossain", "sr@amc.com", 20, 52800, "Cash", "Paid", "", ""),
    ("INV-24076", "2026-07-01", "Tea Garden Mart", "Imran Hossain", "sr@amc.com", 5, 11400, "Cash", "Paid", "", ""),
    ("INV-24077", "2026-06-30", "Padma Trading", "Rashed Khan", "area@amc.com", 72, 312000, "Credit", "Partial", "", "Turnover Champion Q2"),
    ("INV-24078", "2026-06-30", "Karim Stores", "Imran Hossain", "sr@amc.com", 8, 19600, "bKash", "Paid", "BKS1A0QW93", ""),
    ("INV-24079", "2026-06-29", "Hilltop Bazaar", "Imran Hossain", "sr@amc.com", 6, 13800, "Cash", "Paid", "", ""),
    ("INV-24080", "2026-06-29", "Coastal Distributors", "Rashed Khan", "area@amc.com", 30, 104000, "Credit", "Due", "", ""),
    ("INV-24081", "2026-06-28", "Banani Fresh", "Rashed Khan", "area@amc.com", 18, 61200, "Cash", "Paid", "", ""),
]

SALESMEN = [
    ("SR-01", "Imran Hossain", "Dhaka North", "Uttara", 800000, 642000, 38, 12840),
    ("SR-02", "Faisal Rahman", "Dhaka South", "Dhanmondi", 1000000, 1124000, 42, 22480),
    ("SR-03", "Mizan Ahmed", "Chattogram", "Agrabad", 600000, 410000, 31, 6150),
    ("SR-04", "Rakib Islam", "Chattogram", "Halishahar", 1200000, 1380000, 24, 27600),
    ("SR-05", "Sumon Das", "Rajshahi", "Boalia", 1500000, 1820000, 18, 36400),
    ("SR-06", "Tanvir Mahmud", "Sylhet", "Zindabazar", 400000, 286000, 26, 4290),
    ("SR-07", "Kamal Uddin", "Khulna", "Khulna Sadar", 700000, 512000, 22, 10240),
    ("SR-08", "Arif Chowdhury", "Dhaka North", "Mirpur", 900000, 968000, 34, 19360),
]

# id, name, type, start, end, eligible, minQty, reward, accrued, status
OFFERS = [
    ("OFR-101", "Eid Festival Cashback", "Cashback", "2026-06-01", "2026-07-15", "Large, Premium, Distributor", 50, "5% cashback", 248000, "Active"),
    ("OFR-102", "Frozen Quantity Boost", "Quantity Based", "2026-06-10", "2026-08-10", "All categories", 100, "৳15 per box", 86400, "Active"),
    ("OFR-103", "Turnover Champion Q2", "Turnover Based", "2026-04-01", "2026-06-30", "Distributor, Super Distributor", 0, "2% on ৳10L+", 312000, "Active"),
    ("OFR-104", "Loyalty Reward — Tier A", "Loyalty", "2026-01-01", "2026-12-31", "Premium Shop", 0, "Tiered points", 42000, "Active"),
    ("OFR-105", "Buy 10 Get 1 Free", "Free Product", "2026-05-15", "2026-06-15", "Snacks category", 10, "1 free per 10", 18600, "Closed"),
    ("OFR-106", "Monsoon Combo Deal", "Bundle", "2026-06-20", "2026-07-06", "All categories", 20, "৳10 per unit", 15400, "Active"),
]

OFFER_ACCRUALS = [
    ("Sea Breeze Super", "Turnover Champion Q2", 1240000, 24800, "Pending Payout"),
    ("Padma Trading", "Turnover Champion Q2", 1860000, 37200, "Pending Payout"),
    ("City Mart", "Eid Festival Cashback", 612000, 30600, "Pending Payout"),
    ("Rahman Grocers", "Eid Festival Cashback", 245000, 12250, "Accruing"),
    ("Green Valley Mart", "Frozen Quantity Boost", 318000, 8400, "Accruing"),
    ("City Mart", "Buy 10 Get 1 Free", 96000, 4800, "Paid"),
    ("Coastal Distributors", "Turnover Champion Q2", 980000, 19600, "Pending Payout"),
    ("Banani Fresh", "Eid Festival Cashback", 402000, 20100, "Accruing"),
    ("Jessore Wholesale", "Monsoon Combo Deal", 720000, 7200, "Accruing"),
]

# sr_id, name, check_in, check_out, status, visits
ATTENDANCE = [
    ("SR-01", "Imran Hossain", "08:42", "18:10", "Present", 12),
    ("SR-02", "Faisal Rahman", "09:05", "19:22", "Present", 18),
    ("SR-03", "Mizan Ahmed", "—", "—", "Absent", 0),
    ("SR-04", "Rakib Islam", "08:30", "18:05", "Present", 14),
    ("SR-05", "Sumon Das", "08:55", "—", "On Field", 9),
    ("SR-06", "Tanvir Mahmud", "10:20", "18:00", "Late", 11),
    ("SR-07", "Kamal Uddin", "08:48", "17:55", "Present", 10),
    ("SR-08", "Arif Chowdhury", "—", "—", "Absent", 0),
]

LEDGER = [
    ("2026-06-23", "Sales Revenue", 0, 482500, "Income"),
    ("2026-06-23", "Cash in Hand", 154200, 0, "Asset"),
    ("2026-06-23", "Accounts Receivable", 328300, 0, "Asset"),
    ("2026-06-22", "SR Commission", 18600, 0, "Expense"),
    ("2026-06-22", "Offer Reimbursement", 42000, 0, "Expense"),
    ("2026-06-22", "Warehouse Rent", 65000, 0, "Expense"),
    ("2026-06-21", "Vendor Payable — Goldenfield", 0, 184000, "Liability"),
    ("2026-07-03", "Sales Revenue", 0, 261000, "Income"),
    ("2026-07-03", "Cash in Hand", 97000, 0, "Asset"),
    ("2026-07-02", "Fuel & Transport", 21500, 0, "Expense"),
    ("2026-07-01", "bKash Wallet", 91500, 0, "Asset"),
]

# time, srId, sr, shop, outcome, note, followup
VISITS = [
    ("09:12", "SR-01", "Imran Hossain", "Rahman Grocers", "Order placed", "Stocked Eid festival pack", "2026-06-30"),
    ("10:48", "SR-02", "Faisal Rahman", "City Mart", "Order placed", "Discussed turnover offer", "2026-07-02"),
    ("11:30", "SR-04", "Rakib Islam", "Sea Breeze Super", "Collection", "Collected ৳60,000 partial", "—"),
    ("12:15", "SR-05", "Sumon Das", "Padma Trading", "Order placed", "Large order pending PO", "2026-06-25"),
    ("14:05", "SR-06", "Tanvir Mahmud", "Hilltop Bazaar", "Visit only", "Owner unavailable", "2026-06-26"),
    ("09:35", "SR-08", "Arif Chowdhury", "New Market Traders", "Order placed", "Restocked snacks & dairy", "2026-07-08"),
    ("11:10", "SR-07", "Kamal Uddin", "Jessore Wholesale", "Collection", "Collected ৳40,000 against dues", "2026-07-10"),
    ("13:20", "SR-02", "Faisal Rahman", "Banani Fresh", "Order placed", "Premium shelf placement agreed", "2026-07-05"),
]

# id, invoiceId, shop, date, amount, method, txn, note
PAYMENTS = [
    ("PMT-50001", "INV-24061", "Rahman Grocers", "2026-06-23", 28400, "Cash", "", "Full settlement"),
    ("PMT-50002", "INV-24063", "Karim Stores", "2026-06-23", 14800, "bKash", "BKS9F2QX10", "Full settlement"),
    ("PMT-50003", "INV-24064", "Sea Breeze Super", "2026-06-23", 109200, "Cash", "", "Part payment"),
    ("PMT-50004", "INV-24066", "Green Valley Mart", "2026-06-22", 46800, "Cash", "", "Full settlement"),
    ("PMT-50005", "INV-24067", "Hilltop Bazaar", "2026-06-22", 9200, "Cash", "", "Full settlement"),
    ("PMT-50006", "INV-24068", "New Market Traders", "2026-07-03", 18600, "Cash", "", "Full settlement"),
    ("PMT-50007", "INV-24070", "Banani Fresh", "2026-07-03", 78400, "bKash", "BKS7H1MP44", "Full settlement"),
    ("PMT-50008", "INV-24071", "Rahman Grocers", "2026-07-02", 33200, "Cash", "", "Full settlement"),
    ("PMT-50009", "INV-24072", "Sea Breeze Super", "2026-07-02", 120000, "Cash", "", "Part payment"),
    ("PMT-50010", "INV-24074", "City Mart", "2026-07-01", 91500, "bKash", "BKS3K9DZ21", "Full settlement"),
    ("PMT-50011", "INV-24075", "Green Valley Mart", "2026-07-01", 52800, "Cash", "", "Full settlement"),
    ("PMT-50012", "INV-24076", "Tea Garden Mart", "2026-07-01", 11400, "Cash", "", "Full settlement"),
    ("PMT-50013", "INV-24077", "Padma Trading", "2026-06-30", 150000, "Cash", "", "Part payment"),
    ("PMT-50014", "INV-24078", "Karim Stores", "2026-06-30", 19600, "bKash", "BKS1A0QW93", "Full settlement"),
    ("PMT-50015", "INV-24079", "Hilltop Bazaar", "2026-06-29", 13800, "Cash", "", "Full settlement"),
    ("PMT-50016", "INV-24081", "Banani Fresh", "2026-06-28", 61200, "Cash", "", "Full settlement"),
]

# id, shop, date, type, amount, offer, invoiceId, note
CASHBACK = [
    ("CBK-70001", "Sea Breeze Super", "2026-06-20", "Earned", 24800, "Turnover Champion Q2", "", "Accrued"),
    ("CBK-70002", "Padma Trading", "2026-06-20", "Earned", 37200, "Turnover Champion Q2", "", "Accrued"),
    ("CBK-70003", "City Mart", "2026-06-20", "Earned", 30600, "Eid Festival Cashback", "", "Accrued"),
    ("CBK-70004", "Rahman Grocers", "2026-06-20", "Earned", 12250, "Eid Festival Cashback", "", "Accrued"),
    ("CBK-70005", "Green Valley Mart", "2026-06-20", "Earned", 8400, "Frozen Quantity Boost", "", "Accrued"),
    ("CBK-70006", "Coastal Distributors", "2026-06-28", "Earned", 19600, "Turnover Champion Q2", "", "Accrued"),
    ("CBK-70007", "Banani Fresh", "2026-07-01", "Earned", 1568, "Eid Festival Cashback", "", "Earned on INV-24074"),
    ("CBK-70008", "City Mart", "2026-07-01", "Redeemed", 5000, "", "INV-24074", "Applied to INV-24074"),
]


class Command(BaseCommand):
    help = "Seed the database with demo data mirroring the frontend mock data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing rows in the app tables before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing existing data...")
            for model in (
                Payment, CashbackTxn, OfferAccrual, Offer, SalesOrder, Salesman,
                Attendance, LedgerEntry, Visit, Shop, Product,
            ):
                model.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # Users
        for email, name, role, branch, status, is_admin in USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults=dict(
                    name=name, role=role, branch=branch, status=status,
                    is_staff=is_admin, is_superuser=is_admin,
                ),
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()

        # Products (the seed tuples still carry a legacy reorder value; ignored)
        for sku, name, cat, brand, unit, price, stock, _reorder, expiry in PRODUCTS:
            Product.objects.update_or_create(sku=sku, defaults=dict(
                name=name, category=cat, brand=brand, unit=unit, price=price,
                stock=stock, expiry=expiry,
            ))

        # Shops
        for row in SHOPS:
            (code, name, cat, area, terr, zone, dist, thana, owner, phone,
             addr, credit, due, sales30d, sre, srn) = row
            Shop.objects.update_or_create(code=code, defaults=dict(
                name=name, category=cat, area=area, territory=terr, zone=zone,
                district=dist, thana=thana, owner=owner, phone=phone, address=addr,
                credit=credit, due=due, sales30d=sales30d, srEmail=sre, srName=srn,
            ))

        # Sales orders
        for (oid, date, shop, sr, sre, items, amount, pay, status, bkash, offer) in SALES:
            SalesOrder.objects.update_or_create(id=oid, defaults=dict(
                date=date, shop=shop, sr=sr, srEmail=sre, items=items, amount=amount,
                payment=pay, status=status, bkashTxn=bkash, offer=offer,
            ))

        # Salesmen
        for (sid, name, area, terr, target, achieved, shops, comm) in SALESMEN:
            Salesman.objects.update_or_create(id=sid, defaults=dict(
                name=name, area=area, territory=terr, target=target,
                achieved=achieved, shops=shops, commission=comm,
            ))

        # Offers
        for (oid, name, otype, start, end, eligible, minq, reward, accrued, status) in OFFERS:
            Offer.objects.update_or_create(id=oid, defaults=dict(
                name=name, type=otype, start=start, end=end, eligible=eligible,
                minQty=minq, reward=reward, accrued=accrued, status=status,
            ))

        # Offer accruals
        OfferAccrual.objects.all().delete()
        for (shop, offer, purchases, accrued, status) in OFFER_ACCRUALS:
            OfferAccrual.objects.create(
                shop=shop, offer=offer, purchases=purchases, accrued=accrued, status=status,
            )

        # Attendance
        Attendance.objects.all().delete()
        for (sr_id, name, cin, cout, status, visits) in ATTENDANCE:
            Attendance.objects.create(
                sr_id=sr_id, name=name, check_in=cin, check_out=cout,
                status=status, visits=visits,
            )

        # Ledger
        LedgerEntry.objects.all().delete()
        for (date, account, debit, credit, ltype) in LEDGER:
            LedgerEntry.objects.create(
                date=date, account=account, debit=debit, credit=credit, type=ltype,
            )

        # Visits
        Visit.objects.all().delete()
        for (time, srId, sr, shop, outcome, note, followup) in VISITS:
            Visit.objects.create(
                time=time, srId=srId, sr=sr, shop=shop, outcome=outcome,
                note=note, followup=followup,
            )

        # Payments
        for (pid, inv, shop, date, amount, method, txn, note) in PAYMENTS:
            Payment.objects.update_or_create(id=pid, defaults=dict(
                invoiceId=inv, shop=shop, date=date, amount=amount,
                method=method, txn=txn, note=note,
            ))

        # Cashback
        for (cid, shop, date, ctype, amount, offer, inv, note) in CASHBACK:
            CashbackTxn.objects.update_or_create(id=cid, defaults=dict(
                shop=shop, date=date, type=ctype, amount=amount,
                offer=offer, invoiceId=inv, note=note,
            ))

        # --- Settings / master data ------------------------------------
        # Seeded from the constants that used to be hardcoded in the React
        # pages, so existing products and shops keep matching a dropdown entry.
        for name in ["AMC Foods", "Refresho", "Crunchy", "Goldenfield"]:
            Brand.objects.get_or_create(name=name)
        for name in ["PCS", "Box", "Carton", "Bag", "Kg"]:
            Unit.objects.get_or_create(name=name)
        for name in ["Frozen", "Beverage", "Snacks", "Grocery", "Dairy", "Personal Care"]:
            ProductCategory.objects.get_or_create(name=name)
        for name in ["Small Shop", "Medium Shop", "Large Shop", "Premium Shop",
                     "Distributor", "Super Distributor"]:
            ShopCategory.objects.get_or_create(name=name)

        for area_name, zone, territories in AREAS_AND_TERRITORIES:
            area, _ = Area.objects.get_or_create(name=area_name, defaults={"zone": zone})
            for t in territories:
                Territory.objects.get_or_create(name=t, area=area)

        company = CompanySettings.load()
        if not company.tagline:
            company.name = "A.M.C. Agency"
            company.tagline = "Sales Monitoring System"
            company.address = "House 12, Road 5, Uttara, Dhaka 1230"
            company.phone = "+880 1700-000000"
            company.email = "info@amc.com"
            company.website = "www.amc.com"
            company.currency = "৳"
            company.vatBin = "0001234567890"
            company.invoiceFooter = "Thank you for your business."
            company.save()

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {User.objects.count()} users, {Product.objects.count()} products, "
            f"{Shop.objects.count()} shops, {SalesOrder.objects.count()} sales, "
            f"{Offer.objects.count()} offers, {Salesman.objects.count()} salesmen, "
            f"{Payment.objects.count()} payments, {CashbackTxn.objects.count()} cashback txns. "
            f"All accounts use password '{DEMO_PASSWORD}'."
        ))
