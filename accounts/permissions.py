"""
Role-based permissions for the sales-monitoring API.

There are two layers here:

1. PERMS - the *direct* capability matrix. It mirrors the frontend PERMS matrix
   in src/lib/auth.tsx and answers "may this role deliberately edit this module?"

2. DERIVED - the *side-effect* matrix. The business logic lives in the frontend
   (src/pages/sales.tsx, src/lib/payments.ts), and a single user action fans out
   into several collections. Recording one invoice writes:

       /sales/      the invoice          (driver: "sales")
       /payments/   the cash received    (derived)
       /ledger/     revenue + cash rows  (derived)
       /products/   stock decrement      (derived, stock only)
       /shops/      dues + 30d sales     (derived, balance fields only)
       /cashback/   earned / redeemed    (derived)

   Without DERIVED, every role except Super Admin completed only the first two
   calls and got 403 on the rest - stock never decremented and the ledger never
   balanced. A role that may perform the driving action is therefore also
   allowed to write the collections that action necessarily touches.

Derived access is deliberately narrower than direct access:
  - FIELD_LIMITS caps which fields may change (a Sales Officer may move
    Product.stock but not Product.price).
  - DERIVED_CREATABLE controls which derived collections may be created rather
    than only patched.
  - DERIVED_DELETABLE keeps deletes tight; stock and shop rows are never
    deletable as a side effect.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

# ---------------------------------------------------------------------------
# Direct capabilities - keep in sync with PERMS in src/lib/auth.tsx
# ---------------------------------------------------------------------------
PERMS = {
    "Manager": {"write": ["*"], "delete": ["*"]},
    "DSM": {
        "write": ["products", "shops", "sales", "payments", "offers", "targets", "visits"],
        "delete": ["sales", "offers", "visits"],
    },
    "ASM": {
        "write": ["shops", "sales", "payments", "visits", "targets"],
        "delete": ["visits"],
    },
    "ASE": {
        "write": ["shops", "sales", "payments", "visits"],
        "delete": [],
    },
    "SE": {
        "write": ["sales", "payments", "visits", "attendance", "shops"],
        "delete": [],
    },
    "Support Staff": {"write": ["products"], "delete": ["products"]},
    # Collecting cash against an invoice is a different capability from raising
    # one: Administrative may record payments but never create sales orders.
    "Administrative": {"write": ["accounting", "payments"], "delete": ["accounting"]},
}

# ---------------------------------------------------------------------------
# Side-effect capabilities: derived module -> modules whose workflows write it
# ---------------------------------------------------------------------------
DERIVED = {
    "payments": ["sales", "accounting"],
    # The ledger viewset declares module="accounting" (see core/views.py).
    "accounting": ["sales"],
    "products": ["sales"],
    "shops": ["sales", "accounting"],
    "cashback": ["sales", "offers"],
    "offer-accruals": ["sales", "offers"],
    "sales": ["accounting"],
}

# Fields a role may touch when its access is *only* derived.
FIELD_LIMITS = {
    "products": {"stock"},
    "shops": {"due", "sales30d", "credit"},
    "sales": {"paid", "due", "status"},
}

# Derived access that may create rows (everything else is update-only).
DERIVED_CREATABLE = {"payments", "accounting", "cashback", "offer-accruals"}

# Derived access that may delete rows. Stock, shop balances and posted ledger
# entries never qualify - a sale may post to the books but never unpost.
DERIVED_DELETABLE = {"payments", "cashback", "offer-accruals"}

# Keys that identify a row rather than represent a change to it.
IDENTIFIER_KEYS = {"id", "pk", "sku", "code"}


def _direct(role, action, module):
    """True if the role may deliberately perform `action` on `module`."""
    rules = PERMS.get(role, {}).get(action, [])
    return "*" in rules or module in rules


def _derived(role, module):
    """True if any workflow the role may drive necessarily writes `module`."""
    return any(_direct(role, "write", driver) for driver in DERIVED.get(module, []))


def _fields_within_limits(module, data):
    """For derived writes, confirm the payload only touches whitelisted fields."""
    allowed_fields = FIELD_LIMITS.get(module)
    if allowed_fields is None:
        return True
    if not hasattr(data, "keys"):
        return False
    touched = {k for k in data.keys() if k not in IDENTIFIER_KEYS}
    return touched.issubset(allowed_fields)


def allowed(role, method, module, data=None):
    """Resolve a single request against both matrices. Exposed for tests."""
    if method in SAFE_METHODS:
        return True

    if method == "DELETE":
        if _direct(role, "delete", module):
            return True
        return module in DERIVED_DELETABLE and _derived(role, module)

    # POST / PUT / PATCH
    if _direct(role, "write", module):
        return True
    if not _derived(role, module):
        return False
    if method == "POST" and module not in DERIVED_CREATABLE:
        return False
    return _fields_within_limits(module, data if data is not None else {})


class RoleModulePermission(BasePermission):
    """Enforce the matrices above based on the viewset's `module` attribute."""

    message = "Your role does not permit this action on this module."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True

        module = getattr(view, "module", None)
        if module is None:
            # No module declared -> superusers only for writes.
            return request.user.is_superuser

        if allowed(request.user.role, request.method, module, request.data):
            return True

        # Give the caller a usable message instead of a bare 403.
        if module in FIELD_LIMITS and _derived(request.user.role, module):
            self.message = (
                "Your role may only change %s on '%s' as a side effect of "
                "another action." % (sorted(FIELD_LIMITS[module]), module)
            )
        return False
