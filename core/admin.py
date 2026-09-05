from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
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
    ShopReview,
    Target,
    Territory,
    Unit,
    Visit,
)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "shop", "sr", "amount", "payment", "status")
    list_filter = ("payment", "status")
    search_fields = ("id", "shop", "sr")
    inlines = [InvoiceLineInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "segment", "category", "brand", "unit_type", "price", "stock", "total_pcs")
    list_filter = ("segment", "category", "brand", "unit_type")
    search_fields = ("sku", "name")


@admin.register(DamageRecord)
class DamageRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "sku", "productName", "quantity", "unit_type", "damaged_pcs", "reason", "loss_value")
    list_filter = ("reason", "unit_type")
    search_fields = ("id", "sku", "productName", "note")


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ("name", "target_value", "shop_visit_target", "honorarium_type", "honorarium_value", "start_date", "end_date", "status")
    list_filter = ("status", "honorarium_type")
    search_fields = ("name", "description")


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "area", "territory", "dealer", "due", "sales30d")
    list_filter = ("category", "area", "territory")
    search_fields = ("code", "name", "owner")


@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "region", "area", "territory", "ase", "contact_number")
    list_filter = ("region", "area", "territory")
    search_fields = ("code", "name", "contact_number", "address")


admin.site.register(Offer)
admin.site.register(OfferAccrual)
admin.site.register(Salesman)
admin.site.register(Attendance)
admin.site.register(LedgerEntry)
admin.site.register(Visit)
admin.site.register(Payment)
admin.site.register(CashbackTxn)


# --- Settings / master data -------------------------------------------------
class MasterListAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)
    search_fields = ("name",)


admin.site.register(Brand, MasterListAdmin)
admin.site.register(Unit, MasterListAdmin)
admin.site.register(ProductCategory, MasterListAdmin)
admin.site.register(ProductSegment, MasterListAdmin)
admin.site.register(ShopCategory, MasterListAdmin)
admin.site.register(Region, MasterListAdmin)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "region", "zone", "active")
    list_filter = ("active", "zone", "region")
    search_fields = ("name", "zone", "code")


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "area", "active")
    list_filter = ("active", "area")
    search_fields = ("name", "area__name", "code")


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")

    def has_add_permission(self, request):
        # Singleton: edit the existing row rather than adding more.
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# --- HR module ---------------------------------------------------------
class PromotionHistoryInline(admin.TabularInline):
    model = PromotionHistory
    extra = 0


class EmployeeRewardInline(admin.TabularInline):
    model = EmployeeReward
    extra = 0


class EmployeePunishmentInline(admin.TabularInline):
    model = EmployeePunishment
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(BaseUserAdmin):
    """Employee *is* the login account (AUTH_USER_MODEL) — built on Django's
    own UserAdmin so password change/hashing in the admin site works, with
    HR fields folded into the profile section."""

    list_display = ("id_no", "name", "email", "designation", "branch", "status", "joining_date", "salary", "is_staff")
    list_filter = ("designation", "branch", "status", "is_staff")
    search_fields = ("id_no", "name", "email")
    ordering = ("name",)
    inlines = [PromotionHistoryInline, EmployeeRewardInline, EmployeePunishmentInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": (
            "id_no", "name", "designation", "branch", "status",
            "fathers_name", "mothers_name", "date_of_birth",
            "home_district", "permanent_address",
            "joining_date", "salary",
        )}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login")
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("id_no", "email", "name", "designation", "joining_date", "password1", "password2"),
        }),
    )


@admin.register(PromotionHistory)
class PromotionHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "promotion_date", "from_designation", "to_designation")
    list_filter = ("promotion_type",)
    search_fields = ("id", "employee__name")


@admin.register(EmployeeReward)
class EmployeeRewardAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "date", "reward_type", "amount")
    search_fields = ("id", "employee__name")


@admin.register(EmployeePunishment)
class EmployeePunishmentAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "date", "severity", "offense")
    list_filter = ("severity",)
    search_fields = ("id", "employee__name")
