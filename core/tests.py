"""
End-to-end tests for the permission matrix and the multi-collection workflows
the React frontend performs.

The important cases are the *workflows*: the frontend turns one user action into
five or six API calls, and a role that may start a workflow must be able to
finish it. These tests fail loudly if a future permission change reintroduces a
partially-completed sale.

    python manage.py test
"""
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    Area,
    Dealer,
    InvoiceLine,
    LedgerEntry,
    Payment,
    Product,
    Region,
    SalesOrder,
    Shop,
    Territory,
)

User = get_user_model()
PASSWORD = "test-pass-123"

ROLES = {
    "admin@test.com": "Manager",
    "manager@test.com": "DSM",
    "area@test.com": "ASM",
    "sr@test.com": "FSE",
    "warehouse@test.com": "Support Staff",
    "accounts@test.com": "Administrative",
    "hr@test.com": "HR",
}


class BaseAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        for email, role in ROLES.items():
            # `role` is a read-only property (alias for `designation`) on the
            # merged Employee/User model — it isn't a constructor kwarg.
            User.objects.create_user(
                email=email, password=PASSWORD, name=role, designation=role
            )

    def as_role(self, email):
        res = self.client.post(
            "/api/auth/login/",
            {"email": email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def logout(self):
        self.client.credentials()


class AuthTests(BaseAPITest):
    def test_every_seeded_role_can_log_in(self):
        for email in ROLES:
            with self.subTest(email=email):
                self.as_role(email)
                res = self.client.get("/api/auth/me/")
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                self.assertEqual(res.data["email"], email)

    def test_login_rejects_a_bad_password(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "admin@test.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_requests_are_rejected(self):
        self.logout()
        self.assertEqual(
            self.client.get("/api/products/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_every_collection_is_readable_by_any_role(self):
        endpoints = [
            "products", "shops", "sales", "offers", "offer-accruals",
            "salesmen", "attendance", "ledger", "visits", "payments",
            "cashback-txns",
        ]
        self.as_role("warehouse@test.com")
        for ep in endpoints:
            with self.subTest(endpoint=ep):
                self.assertEqual(
                    self.client.get(f"/api/{ep}/").status_code,
                    status.HTTP_200_OK,
                )


class SaleWorkflowTests(BaseAPITest):
    """One invoice = six writes. Any role that may sell must complete all six."""

    def setUp(self):
        self.product = Product.objects.create(
            sku="SKU-T1", name="Test Product", category="C", brand="B",
            unit="pc", price=Decimal("250.00"), stock=100,
        )
        self.shop = Shop.objects.create(
            code="SHP-T1", name="Test Shop", category="Retail",
            area="A", territory="T", owner="Owner", due=Decimal("0"),
            sales30d=Decimal("0"),
        )

    def _sell(self, invoice_id):
        """Replay exactly what src/pages/sales.tsx writes for one cash sale."""
        results = {}
        results["invoice"] = self.client.post(
            "/api/sales/",
            {
                "id": invoice_id, "date": "2026-07-18", "shop": "Test Shop",
                "sr": "Imran", "items": 1, "amount": 500, "paid": 500, "due": 0,
                "payment": "Cash", "status": "Paid",
                "lines": [{"sku": "SKU-T1", "name": "Test Product", "qty": 2, "price": 250}],
            },
            format="json",
        )
        results["payment"] = self.client.post(
            "/api/payments/",
            {
                "id": f"PMT-{invoice_id}", "invoiceId": invoice_id,
                "shop": "Test Shop", "date": "2026-07-18", "amount": 500,
                "method": "Cash",
            },
            format="json",
        )
        results["ledger_revenue"] = self.client.post(
            "/api/ledger/",
            {"date": "2026-07-18", "account": "Sales Revenue", "debit": 0,
             "credit": 500, "type": "Income", "ref": invoice_id},
            format="json",
        )
        results["ledger_cash"] = self.client.post(
            "/api/ledger/",
            {"date": "2026-07-18", "account": "Cash in Hand", "debit": 500,
             "credit": 0, "type": "Asset", "ref": invoice_id},
            format="json",
        )
        results["stock"] = self.client.patch(
            "/api/products/SKU-T1/", {"stock": 98}, format="json"
        )
        results["shop_balance"] = self.client.patch(
            "/api/shops/SHP-T1/", {"sales30d": 500, "due": 0}, format="json"
        )
        return results

    def test_selling_roles_complete_the_entire_workflow(self):
        # Pinned well inside the default 10:05-19:00 shift window so this
        # doesn't flake depending on what time of day the suite happens to
        # run (SalesOrderSerializer rejects a new sale before shift start).
        midday = timezone.make_aware(datetime(2026, 7, 18, 14, 0))
        for email in ["admin@test.com", "manager@test.com", "area@test.com", "sr@test.com"]:
            with self.subTest(role=ROLES[email]):
                Product.objects.filter(sku="SKU-T1").update(stock=100)
                self.as_role(email)
                with patch("django.utils.timezone.now", return_value=midday):
                    results = self._sell(f"INV-{email[:3].upper()}")
                for step, res in results.items():
                    self.assertIn(
                        res.status_code,
                        (status.HTTP_200_OK, status.HTTP_201_CREATED),
                        f"{ROLES[email]} failed at '{step}': "
                        f"{res.status_code} {getattr(res, 'data', '')}",
                    )
                self.product.refresh_from_db()
                self.assertEqual(self.product.stock, 98, "stock was not decremented")

    def test_a_sale_leaves_the_ledger_balanced(self):
        self.as_role("sr@test.com")
        midday = timezone.make_aware(datetime(2026, 7, 18, 14, 0))
        with patch("django.utils.timezone.now", return_value=midday):
            self._sell("INV-BAL")
        rows = LedgerEntry.objects.filter(ref="INV-BAL")
        self.assertEqual(rows.count(), 2)
        debits = sum(r.debit for r in rows)
        credits = sum(r.credit for r in rows)
        self.assertEqual(debits, credits, "ledger entries do not balance")

    def test_non_selling_roles_cannot_start_the_workflow(self):
        for email in ["warehouse@test.com", "accounts@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.post(
                    "/api/sales/",
                    {"id": f"INV-NO-{email[:3]}", "date": "2026-07-18",
                     "shop": "Test Shop", "sr": "X", "items": 1, "amount": 1,
                     "paid": 0, "due": 1, "payment": "Credit", "status": "Due"},
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class PaymentWorkflowTests(BaseAPITest):
    """Collecting cash against an existing invoice — the Accountant's job."""

    def setUp(self):
        self.shop = Shop.objects.create(
            code="SHP-P1", name="Payer Shop", category="Retail", area="A",
            territory="T", owner="O", due=Decimal("500.00"),
        )
        self.invoice = SalesOrder.objects.create(
            id="INV-PAY", date="2026-07-01", shop="Payer Shop", sr="Imran",
            items=1, amount=Decimal("500"), paid=Decimal("0"),
            due=Decimal("500"), payment="Credit", status="Due",
        )

    def _collect(self, payment_id):
        return {
            "payment": self.client.post(
                "/api/payments/",
                {"id": payment_id, "invoiceId": "INV-PAY", "shop": "Payer Shop",
                 "date": "2026-07-18", "amount": 500, "method": "Cash"},
                format="json",
            ),
            "invoice": self.client.patch(
                "/api/sales/INV-PAY/",
                {"paid": 500, "due": 0, "status": "Paid"},
                format="json",
            ),
            "shop": self.client.patch(
                "/api/shops/SHP-P1/", {"due": 0}, format="json"
            ),
            "ledger_cash": self.client.post(
                "/api/ledger/",
                {"date": "2026-07-18", "account": "Cash in Hand", "debit": 500,
                 "credit": 0, "type": "Asset", "ref": "INV-PAY"},
                format="json",
            ),
            "ledger_ar": self.client.post(
                "/api/ledger/",
                {"date": "2026-07-18", "account": "Accounts Receivable",
                 "debit": 0, "credit": 500, "type": "Asset", "ref": "INV-PAY"},
                format="json",
            ),
        }

    def test_accountant_can_complete_a_collection(self):
        self.as_role("accounts@test.com")
        for step, res in self._collect("PMT-ACC").items():
            self.assertIn(
                res.status_code,
                (status.HTTP_200_OK, status.HTTP_201_CREATED),
                f"Accountant failed at '{step}': {res.status_code} {getattr(res, 'data', '')}",
            )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "Paid")
        self.assertEqual(self.invoice.due, Decimal("0"))

    def test_sales_officer_can_also_collect(self):
        self.as_role("sr@test.com")
        for step, res in self._collect("PMT-SR").items():
            self.assertIn(
                res.status_code,
                (status.HTTP_200_OK, status.HTTP_201_CREATED),
                f"Sales Officer failed at '{step}': {res.status_code}",
            )

    def test_warehouse_manager_cannot_collect(self):
        self.as_role("warehouse@test.com")
        res = self.client.post(
            "/api/payments/",
            {"id": "PMT-WH", "invoiceId": "INV-PAY", "shop": "Payer Shop",
             "date": "2026-07-18", "amount": 500, "method": "Cash"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Payment.objects.count(), 0)


class DerivedAccessLimitTests(BaseAPITest):
    """Side-effect access must stay narrower than direct access."""

    def setUp(self):
        Product.objects.create(
            sku="SKU-L1", name="Limited", category="C", brand="B", unit="pc",
            price=Decimal("100.00"), stock=50,
        )

    def test_sales_officer_may_move_stock(self):
        self.as_role("sr@test.com")
        res = self.client.patch("/api/products/SKU-L1/", {"stock": 40}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_sales_officer_may_not_change_price(self):
        self.as_role("sr@test.com")
        res = self.client.patch("/api/products/SKU-L1/", {"price": 1}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Product.objects.get(sku="SKU-L1").price, Decimal("100.00"))

    def test_sales_officer_may_not_create_a_product(self):
        self.as_role("sr@test.com")
        res = self.client.post(
            "/api/products/",
            {"sku": "SKU-NEW", "name": "N", "category": "C", "brand": "B",
             "unit": "pc", "price": 10, "stock": 1},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_officer_may_not_delete_a_product(self):
        self.as_role("sr@test.com")
        res = self.client.delete("/api/products/SKU-L1/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(sku="SKU-L1").exists())

    def test_warehouse_manager_keeps_full_product_control(self):
        self.as_role("warehouse@test.com")
        self.assertEqual(
            self.client.patch("/api/products/SKU-L1/", {"price": 120}, format="json").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.delete("/api/products/SKU-L1/").status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_accountant_may_settle_an_invoice_but_not_rewrite_it(self):
        SalesOrder.objects.create(
            id="INV-LIM", date="2026-07-01", shop="S", sr="X", items=1,
            amount=Decimal("100"), paid=Decimal("0"), due=Decimal("100"),
            payment="Credit", status="Due",
        )
        self.as_role("accounts@test.com")
        ok = self.client.patch(
            "/api/sales/INV-LIM/", {"paid": 100, "due": 0, "status": "Paid"}, format="json"
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        denied = self.client.patch(
            "/api/sales/INV-LIM/", {"amount": 99999}, format="json"
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)


class EmployeeAuthTests(BaseAPITest):
    """core.Employee is the login account itself (AUTH_USER_MODEL) — there's
    no separate /api/auth/users/ anymore. Employee CRUD lives at
    /api/employees/, gated to the 'hr' module: Manager (via '*') and the
    dedicated HR role may create/edit employees; nobody else can."""

    def _payload(self, **overrides):
        payload = {
            "id_no": "EMP-900", "name": "New", "email": "new@test.com",
            "designation": "FSE", "joining_date": "2026-07-01",
            "salary": 30000, "password": "secret-pass-1",
        }
        payload.update(overrides)
        return payload

    def test_manager_and_hr_may_create_employees(self):
        for email, id_no in [("admin@test.com", "EMP-901"), ("hr@test.com", "EMP-902")]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.post(
                    "/api/employees/",
                    self._payload(id_no=id_no, email=f"{id_no}@test.com"),
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
                self.assertNotIn("password", res.data)

    def test_other_roles_cannot_create_employees(self):
        for email in ["manager@test.com", "sr@test.com", "accounts@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.post(
                    "/api/employees/",
                    self._payload(id_no=f"EMP-{email[:3]}", email=f"x-{email}"),
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_created_employee_can_log_in_with_the_given_password(self):
        self.as_role("admin@test.com")
        self.client.post(
            "/api/employees/",
            self._payload(id_no="EMP-903", email="fresh@test.com", password="fresh-pass-99"),
            format="json",
        )
        self.logout()
        res = self.client.post(
            "/api/auth/login/",
            {"email": "fresh@test.com", "password": "fresh-pass-99"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class AttendanceTests(BaseAPITest):
    def test_sales_officer_can_check_in_and_out(self):
        self.as_role("sr@test.com")
        created = self.client.post(
            "/api/attendance/",
            {"id": "SR-01", "name": "Imran", "email": "sr@test.com",
             "in": "09:05", "out": "", "status": "Present", "visits": 0,
             "date": "2026-07-18"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        # The serializer renames check_in/check_out back to in/out for the UI.
        self.assertEqual(created.data["in"], "09:05")
        self.assertEqual(created.data["id"], "SR-01")

        pk = created.data["pk"]
        updated = self.client.patch(
            f"/api/attendance/{pk}/", {"out": "18:30"}, format="json"
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["out"], "18:30")

    def test_warehouse_manager_cannot_post_attendance(self):
        self.as_role("warehouse@test.com")
        res = self.client.post(
            "/api/attendance/",
            {"id": "SR-02", "name": "X", "status": "Present", "visits": 0,
             "date": "2026-07-18"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class SettingsTests(BaseAPITest):
    """Master data: everyone reads, only Super Admin writes."""

    LISTS = ["brands", "units", "product-categories", "shop-categories", "areas"]

    def setUp(self):
        from core.models import Area, Brand, Territory
        Brand.objects.create(name="AMC Foods")
        self.area = Area.objects.create(name="Dhaka North", zone="Dhaka")
        Territory.objects.create(name="Uttara", area=self.area)

    def test_every_role_can_read_the_lists(self):
        for email in ROLES:
            self.as_role(email)
            for ep in self.LISTS + ["territories", "company"]:
                with self.subTest(role=ROLES[email], endpoint=ep):
                    self.assertEqual(
                        self.client.get(f"/api/{ep}/").status_code, status.HTTP_200_OK
                    )

    def test_only_manager_can_write_the_lists(self):
        # Settings (master data) is Super Admin-only as of the 2026-10 change
        # that locked it down from "all except Accounts & HR" — DSM/ASM lost
        # direct settings write then, same as everyone but Manager.
        self.as_role("admin@test.com")
        for ep in self.LISTS:
            with self.subTest(endpoint=ep):
                res = self.client.post(f"/api/{ep}/", {"name": f"New {ep} by Manager"}, format="json")
                self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_other_roles_cannot_write_the_lists(self):
        for email in ["manager@test.com", "area@test.com", "sr@test.com", "warehouse@test.com", "accounts@test.com", "hr@test.com"]:
            self.as_role(email)
            for ep in self.LISTS:
                with self.subTest(role=ROLES[email], endpoint=ep):
                    res = self.client.post(f"/api/{ep}/", {"name": "Sneaky"}, format="json")
                    self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_territory_is_created_and_read_by_area_name(self):
        self.as_role("admin@test.com")
        res = self.client.post(
            "/api/territories/", {"name": "Mirpur", "area": "Dhaka North"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["area"], "Dhaka North")

    def test_territory_names_are_unique_per_area_only(self):
        self.as_role("admin@test.com")
        dup = self.client.post(
            "/api/territories/", {"name": "Uttara", "area": "Dhaka North"}, format="json"
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)

        from core.models import Area
        Area.objects.create(name="Sylhet")
        ok = self.client.post(
            "/api/territories/", {"name": "Uttara", "area": "Sylhet"}, format="json"
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

    def test_territories_can_be_filtered_by_area(self):
        self.as_role("sr@test.com")
        res = self.client.get(f"/api/territories/?area={self.area.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(all(r["area"] == "Dhaka North" for r in res.data["results"]))

    def test_deleting_an_area_still_in_use_returns_400_not_500(self):
        self.as_role("admin@test.com")
        res = self.client.delete(f"/api/areas/{self.area.id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("still in use", res.data["detail"])

    def test_company_is_a_singleton_that_super_admin_can_edit(self):
        self.as_role("admin@test.com")
        listing = self.client.get("/api/company/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 1, "company must be exactly one row")

        res = self.client.patch(
            "/api/company/1/",
            {"name": "A.M.C. Agency Ltd", "logo": "data:image/png;base64,AAA"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "A.M.C. Agency Ltd")

        self.as_role("sr@test.com")
        denied = self.client.patch("/api/company/1/", {"name": "Nope"}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get("/api/company/").data[0]["name"], "A.M.C. Agency Ltd"
        )


class DiscountPaymentTests(BaseAPITest):
    """A discount given on delivery reduces the due without inflating cash."""

    def setUp(self):
        self.shop = Shop.objects.create(
            code="SHP-D1", name="Discount Shop", category="Retail", area="A",
            territory="T", owner="O", due=Decimal("1000.00"),
        )
        self.invoice = SalesOrder.objects.create(
            id="INV-DISC", date="2026-07-01", shop="Discount Shop", sr="Imran",
            items=1, amount=Decimal("1000"), paid=Decimal("0"),
            due=Decimal("1000"), payment="Credit", status="Due",
        )

    def test_discount_method_payment_is_recorded_and_readable(self):
        self.as_role("sr@test.com")
        res = self.client.post(
            "/api/payments/",
            {"id": "PMT-DISC", "invoiceId": "INV-DISC", "shop": "Discount Shop",
             "date": "2026-07-18", "amount": 150, "method": "Discount",
             "note": "Discount given on delivery"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["method"], "Discount")

        listing = self.client.get("/api/payments/?invoiceId=INV-DISC")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        methods = [p["method"] for p in listing.data["results"]]
        self.assertIn("Discount", methods)


class DealerHierarchyTests(BaseAPITest):
    """Region -> Area -> Territory -> ASE -> Dealer -> Shop CRUD + report."""

    def setUp(self):
        self.region = Region.objects.create(name="Central-1")
        self.area = Area.objects.create(name="Dhaka North", code="A-01", region=self.region)
        self.territory = Territory.objects.create(name="Chawkbazar", code="T-001", area=self.area)
        # Dealer.ase links to Employee (any HR designation, DSM/ASM/ASE/...),
        # not the separate Salesman table.
        self.ase = User.objects.create_user(
            id_no="AMC-011", email="amc011@test.com", password=PASSWORD,
            name="Md. Sharif", designation="ASE",
        )

    def test_manager_can_create_a_dealer_with_the_full_hierarchy(self):
        self.as_role("admin@test.com")
        res = self.client.post(
            "/api/dealers/",
            {"code": "WS00001", "name": "Sanam Enterprise", "region": "Central-1",
             "area": "Dhaka North", "territory": "Chawkbazar", "ase": "AMC-011",
             "contact_number": "0171", "address": "Addr 1"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["area_code"], "A-01")
        self.assertEqual(res.data["territory_code"], "T-001")
        self.assertEqual(res.data["ase_name"], "Md. Sharif")

    def test_dsm_can_create_a_dealer_like_a_shop(self):
        # Dealer reuses the "shops" module's permissions; DSM has direct
        # "shops" write under the 2026-09 "all except Accounts & HR" scope.
        self.as_role("manager@test.com")
        res = self.client.post(
            "/api/dealers/",
            {"code": "WS00002", "name": "Sifat Enterprise", "area": "Dhaka North",
             "territory": "Chawkbazar"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_fse_cannot_create_a_dealer(self):
        # FSE (ex-SE) is scoped down to Sales/Attendance/Visits only under
        # the 2026-09 redesign — no direct or derived "shops" create access.
        self.as_role("sr@test.com")
        res = self.client.post(
            "/api/dealers/",
            {"code": "WS00003", "name": "Nope Enterprise", "area": "Dhaka North",
             "territory": "Chawkbazar"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_staff_cannot_create_a_dealer(self):
        self.as_role("warehouse@test.com")
        res = self.client.post(
            "/api/dealers/",
            {"code": "WS00003", "name": "Nope Enterprise", "area": "Dhaka North",
             "territory": "Chawkbazar"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_manager_can_write_region(self):
        self.as_role("admin@test.com")
        ok = self.client.post("/api/regions/", {"name": "West-1"}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED, ok.data)

        self.as_role("sr@test.com")
        denied = self.client.post("/api/regions/", {"name": "Sneaky"}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)


class ProductSalesReportTests(BaseAPITest):
    """MTD/YTD product-wise sales report — the Excel export's data source."""

    def setUp(self):
        self.region = Region.objects.create(name="Central-1")
        self.area = Area.objects.create(name="Dhaka North", code="A-01", region=self.region)
        self.territory = Territory.objects.create(name="Chawkbazar", code="T-001", area=self.area)
        self.ase = User.objects.create_user(
            id_no="AMC-011", email="amc011-rpt@test.com", password=PASSWORD,
            name="Md. Sharif", designation="ASE",
        )
        self.dealer = Dealer.objects.create(
            code="WS00001", name="Sanam Enterprise", region="Central-1",
            area="Dhaka North", territory="Chawkbazar", ase=self.ase,
        )
        self.shop = Shop.objects.create(
            code="SHP-R1", name="Report Shop", category="Retail", area="Dhaka North",
            territory="Chawkbazar", owner="O", dealer=self.dealer,
        )
        self.product = Product.objects.create(
            sku="RPT-001", name="Report Product", category="C", brand="Brand",
            unit_type="PCS", price=Decimal("100.00"), stock=100,
        )
        import datetime
        today = datetime.date.today().isoformat()
        order = SalesOrder.objects.create(
            id="INV-RPT", date=today, shop="Report Shop", sr="Imran", items=1,
            amount=Decimal("3000"), paid=Decimal("3000"), due=Decimal("0"),
            payment="Cash", status="Paid",
        )
        InvoiceLine.objects.create(order=order, sku="RPT-001", name="Report Product", qty=30, price=Decimal("100"))

    def test_report_aggregates_the_dealers_sale(self):
        self.as_role("admin@test.com")
        res = self.client.get("/api/reports/product-sales/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data["rows"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["dealerCode"], "WS00001")
        self.assertEqual(row["region"], "Central-1")
        self.assertEqual(row["areaCode"], "A-01")
        self.assertEqual(row["territoryCode"], "T-001")
        self.assertEqual(row["aseCode"], "AMC-011")
        self.assertEqual(row["mtd"]["RPT-001"]["value"], 3000.0)
        self.assertEqual(row["mtd"]["RPT-001"]["volume"], "30 PCS")
        self.assertEqual(row["ytd"]["RPT-001"]["value"], 3000.0)

    def test_report_filters_by_region(self):
        self.as_role("admin@test.com")
        matching = self.client.get("/api/reports/product-sales/?region=Central-1")
        self.assertEqual(len(matching.data["rows"]), 1)
        other = self.client.get("/api/reports/product-sales/?region=West-1")
        self.assertEqual(len(other.data["rows"]), 0)

    def test_report_excel_export_downloads(self):
        self.as_role("sr@test.com")  # any authenticated role may read the report
        res = self.client.get("/api/reports/product-sales/?ext=xlsx")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_anonymous_cannot_read_the_report(self):
        self.logout()
        res = self.client.get("/api/reports/product-sales/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class RoleScopeTests(BaseAPITest):
    """The 2026-09 role redesign: DSM/ASM get everything except Accounting
    and HR; ASE/FSE get only Sales/Attendance/Visits; Administrative
    (Accounts & Finance) gets only Accounting+Payments; HR gets only
    Employees+Attendance."""

    def test_dsm_and_asm_still_post_ledger_entries_as_a_sale_side_effect(self):
        # "Without the Accounts & HR part" removes their direct PERMS entry
        # for "accounting" (so the Account & Finance *page* is hidden on the
        # frontend), but posting a sale's ledger rows is an intrinsic part of
        # completing a sale — DERIVED["accounting"] = ["sales"] still grants
        # it, exactly like it always has for every selling role.
        for email in ["manager@test.com", "area@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.post(
                    "/api/ledger/",
                    {"date": "2026-07-18", "account": "Misc", "debit": 1, "credit": 0, "type": "Asset"},
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_dsm_and_asm_cannot_write_hr(self):
        for email in ["manager@test.com", "area@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.post(
                    "/api/employees/",
                    {"id_no": "EMP-950", "name": "X", "email": f"x-{email}",
                     "designation": "FSE", "joining_date": "2026-07-01", "password": "x"},
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_ase_and_fse_are_restricted_to_sales_attendance_visits(self):
        Product.objects.create(
            sku="SKU-RS1", name="Restricted", category="C", brand="B",
            unit="pc", price=Decimal("10.00"), stock=10,
        )
        for email in ["sr@test.com"]:  # FSE seeded; ASE behaves identically (same PERMS entry)
            self.as_role(email)
            denied_product = self.client.post(
                "/api/products/",
                {"sku": "SKU-NEW2", "name": "N", "category": "C", "brand": "B", "unit": "pc", "price": 1, "stock": 1},
                format="json",
            )
            self.assertEqual(denied_product.status_code, status.HTTP_403_FORBIDDEN)
            denied_offer = self.client.post(
                "/api/offers/", {"id": "OFR-X", "name": "X", "type": "Discount"}, format="json"
            )
            self.assertEqual(denied_offer.status_code, status.HTTP_403_FORBIDDEN)
            allowed_visit = self.client.post(
                "/api/visits/",
                {"date": "2026-07-18", "time": "09:00", "sr": "X", "shop": "Test Shop", "outcome": "Sale"},
                format="json",
            )
            self.assertEqual(allowed_visit.status_code, status.HTTP_201_CREATED, allowed_visit.data)

    def test_administrative_cannot_write_sales_or_hr(self):
        self.as_role("accounts@test.com")
        denied_sales = self.client.post(
            "/api/sales/",
            {"id": "INV-ADM", "date": "2026-07-18", "shop": "X", "sr": "X", "amount": 1, "payment": "Cash", "status": "Due"},
            format="json",
        )
        self.assertEqual(denied_sales.status_code, status.HTTP_403_FORBIDDEN)
        denied_hr = self.client.post(
            "/api/employees/",
            {"id_no": "EMP-951", "name": "X", "email": "x@test.com",
             "designation": "FSE", "joining_date": "2026-07-01", "password": "x"},
            format="json",
        )
        self.assertEqual(denied_hr.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_cannot_write_accounting_or_sales(self):
        self.as_role("hr@test.com")
        denied_ledger = self.client.post(
            "/api/ledger/",
            {"date": "2026-07-18", "account": "Misc", "debit": 1, "credit": 0, "type": "Asset"},
            format="json",
        )
        self.assertEqual(denied_ledger.status_code, status.HTTP_403_FORBIDDEN)
        denied_sales = self.client.post(
            "/api/sales/",
            {"id": "INV-HR", "date": "2026-07-18", "shop": "X", "sr": "X", "amount": 1, "payment": "Cash", "status": "Due"},
            format="json",
        )
        self.assertEqual(denied_sales.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_can_write_attendance(self):
        self.as_role("hr@test.com")
        res = self.client.post(
            "/api/attendance/",
            {"id": "SR-HR1", "name": "X", "status": "Present", "visits": 0, "date": "2026-07-18"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)


class RowVisibilityTests(BaseAPITest):
    """Row-level read scoping (core/visibility.py): a role may be allowed to
    *write* a module company-wide, but that's a different axis from whose
    *rows* it can read back — Manager sees everything; everyone else sees
    self + downline (DSM -> ASM -> ASE -> FSE via Employee.reports_to)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        dsm = User.objects.get(email="manager@test.com")  # role DSM
        asm = User.objects.get(email="area@test.com")  # role ASM
        asm.reports_to = dsm
        asm.save()
        fse = User.objects.get(email="sr@test.com")  # role FSE
        fse.reports_to = asm
        fse.save()
        # An unrelated branch: HR has no downline and reports to nobody.
        cls.outsider_email = "hr@test.com"

        Shop.objects.create(
            code="SHP-VIS1", name="FSE Shop", category="Retail", area="A",
            territory="T", owner="O", srEmail=fse.email, srName=fse.name,
        )
        Shop.objects.create(
            code="SHP-VIS2", name="Outsider Shop", category="Retail", area="A",
            territory="T", owner="O", srEmail=cls.outsider_email, srName="Outsider",
        )

    def _shop_codes(self):
        res = self.client.get("/api/shops/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return {s["code"] for s in res.data["results"]}

    def test_manager_sees_every_shop(self):
        self.as_role("admin@test.com")
        codes = self._shop_codes()
        self.assertIn("SHP-VIS1", codes)
        self.assertIn("SHP-VIS2", codes)

    def test_dsm_sees_downline_shop_not_unrelated_one(self):
        # DSM -> ASM -> FSE: the DSM should see the FSE's shop (two levels
        # down) but not a shop belonging to someone outside the hierarchy.
        self.as_role("manager@test.com")
        codes = self._shop_codes()
        self.assertIn("SHP-VIS1", codes)
        self.assertNotIn("SHP-VIS2", codes)

    def test_fse_sees_only_its_own_shop(self):
        self.as_role("sr@test.com")
        codes = self._shop_codes()
        self.assertIn("SHP-VIS1", codes)
        self.assertNotIn("SHP-VIS2", codes)

    def test_hr_data_is_redacted_for_other_roles_but_not_for_self(self):
        User.objects.filter(email="sr@test.com").update(salary=Decimal("30000"))
        self.as_role("sr@test.com")
        own = self.client.get("/api/employees/").data["results"]
        mine = next(e for e in own if e["email"] == "sr@test.com")
        someone_else = next(e for e in own if e["email"] != "sr@test.com")
        self.assertIn("salary", mine)
        self.assertNotIn("salary", someone_else)
        # The directory itself (name/email/designation) must stay visible to
        # everyone — pickers across the app depend on the full list.
        self.assertEqual(len(own), len(ROLES))

    def test_hr_role_sees_everyones_sensitive_fields(self):
        User.objects.filter(email="sr@test.com").update(salary=Decimal("30000"))
        self.as_role("hr@test.com")
        rows = self.client.get("/api/employees/").data["results"]
        sr = next(e for e in rows if e["email"] == "sr@test.com")
        self.assertIn("salary", sr)

    def test_ledger_is_manager_and_administrative_only(self):
        LedgerEntry.objects.create(date="2026-07-18", account="Misc", debit=1, credit=0, type="Asset")
        for email in ["admin@test.com", "accounts@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.get("/api/ledger/")
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                self.assertGreaterEqual(len(res.data["results"]), 1)
        for email in ["manager@test.com", "area@test.com", "sr@test.com", "warehouse@test.com", "hr@test.com"]:
            with self.subTest(role=ROLES[email]):
                self.as_role(email)
                res = self.client.get("/api/ledger/")
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                self.assertEqual(res.data["results"], [])
