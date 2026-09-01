from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    public_invoice,
    product_sales_report,
    AccountHeadViewSet,
    AreaViewSet,
    AttendanceViewSet,
    BrandViewSet,
    CashbackTxnViewSet,
    CompanySettingsViewSet,
    DamageRecordViewSet,
    DealerViewSet,
    EmployeePunishmentViewSet,
    EmployeeRewardViewSet,
    EmployeeViewSet,
    ExpenseHeadViewSet,
    LedgerEntryViewSet,
    OfferAccrualViewSet,
    OfferViewSet,
    PaymentViewSet,
    PayoutViewSet,
    ProductCategoryViewSet,
    ProductSegmentViewSet,
    ProductViewSet,
    PromotionHistoryViewSet,
    RegionViewSet,
    SalesOrderViewSet,
    SalesmanViewSet,
    ShopCategoryViewSet,
    ShopReviewViewSet,
    ShopViewSet,
    TargetViewSet,
    TerritoryViewSet,
    UnitViewSet,
    VisitViewSet,
)

router = DefaultRouter()
# Endpoint names align with the frontend COLLECTIONS keys in src/lib/store.ts
router.register("products", ProductViewSet)
router.register("dealers", DealerViewSet)
router.register("shops", ShopViewSet)
router.register("sales", SalesOrderViewSet)
router.register("offers", OfferViewSet)
router.register("offer-accruals", OfferAccrualViewSet)
router.register("salesmen", SalesmanViewSet)
router.register("attendance", AttendanceViewSet)
router.register("ledger", LedgerEntryViewSet)
router.register("visits", VisitViewSet)
router.register("payments", PaymentViewSet)
router.register("payouts", PayoutViewSet)
router.register("cashback-txns", CashbackTxnViewSet)
router.register("shop-reviews", ShopReviewViewSet)
router.register("targets", TargetViewSet)
router.register("damage-records", DamageRecordViewSet)

# HR Module
router.register("employees", EmployeeViewSet)
router.register("promotion-histories", PromotionHistoryViewSet)
router.register("employee-rewards", EmployeeRewardViewSet)
router.register("employee-punishments", EmployeePunishmentViewSet)

# Settings / master data (Super Admin writes, everyone reads)
router.register("brands", BrandViewSet)
router.register("units", UnitViewSet)
router.register("product-categories", ProductCategoryViewSet)
router.register("product-segments", ProductSegmentViewSet)
router.register("account-heads", AccountHeadViewSet)
router.register("expense-heads", ExpenseHeadViewSet)
router.register("shop-categories", ShopCategoryViewSet)
router.register("regions", RegionViewSet)
router.register("areas", AreaViewSet)
router.register("territories", TerritoryViewSet)
router.register("company", CompanySettingsViewSet, basename="company")

urlpatterns = [
    # Unauthenticated, token-gated invoice read — the target of the printed QR.
    path("public/invoice/<str:invoice_id>/", public_invoice, name="public-invoice"),
    path("reports/product-sales/", product_sales_report, name="product-sales-report"),
    *router.urls,
]
