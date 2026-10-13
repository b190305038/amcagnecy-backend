"""
Row-level read scoping — "whose data can this user see", layered on top of
accounts/permissions.py (which only answers "may this role write/delete this
module"). Until this module existed, every list/read endpoint returned every
row to any authenticated user regardless of role: the frontend hid some of it
in a few places (sales.tsx, attendance.tsx, reports.tsx), but that's a display
choice, trivially bypassed by calling the API directly — there was no actual
enforcement. This is that enforcement, applied via each ViewSet's
`get_queryset()`.

The policy, consistent with how the hierarchy is already used elsewhere
(sales creation, Reports, Attendance, View As):

  - Manager (Super Admin) sees everything, everywhere.
  - Everyone else sees their own rows plus their downline's (DSM -> ASM ->
    ASE -> FSE, via Employee.reports_to / downline()) for sales-floor data —
    *not* "everything they could write to". A DSM can write company-wide
    under the module matrix, but that's a different axis from whose rows
    they can read.
  - HR module data (salary, DOB, address, promotion/reward/punishment
    history) is tighter still: only Manager and HR see anyone else's row at
    all; every other role sees only their own Employee record.
  - Accounting's general ledger is tighter again: Manager and Administrative
    only — no sales-floor role has ever had any access to it, read or write.
  - Money that flows through a specific outlet (Payment, Payout, CashbackTxn,
    OfferAccrual) has no direct employee/email field, only a shop name — so
    it's scoped indirectly, through which employee that Shop is assigned to
    (Shop.srEmail).

Several of these models only carry a free-text name or email snapshot, not a
real foreign key (the Employee/Salesman split predates this module and is a
known, separately-tracked piece of debt). Where a row's identifying text
doesn't match any known Employee at all, it's left visible to everyone rather
than silently hidden — a row scoping can't confidently attribute to anyone
is far more likely stale/legacy data than something to actively hide, and
the failure mode of "hide real data from someone who should see it" is worse
than "an unscoped legacy row remains visible a little too broadly".
"""
from django.db.models import Q

#: Roles with no restriction at all — see every row.
EVERYTHING = {"Manager"}


def downline_names_and_emails(user):
    """(names, emails) for `user` plus everyone in their downline."""
    names = {user.name}
    emails = {user.email}
    for e in user.downline():
        names.add(e.name)
        emails.add(e.email)
    return names, emails


def scope_by_email(qs, user, field, full_roles=EVERYTHING):
    """Filter `qs` to rows whose `field` (an email) belongs to the user or
    their downline. A row whose email doesn't match any known Employee login
    passes through unscoped (see module docstring)."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in full_roles:
        return qs
    from .models import Employee

    _, emails = downline_names_and_emails(user)
    known = set(Employee.objects.exclude(email="").values_list("email", flat=True))
    return qs.filter(Q(**{f"{field}__in": emails}) | ~Q(**{f"{field}__in": known}))


def scope_by_name(qs, user, field, full_roles=EVERYTHING):
    """Same as scope_by_email, but matching on a plain name field — used
    where the model has no email at all (e.g. Visit.sr, Salesman.name)."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in full_roles:
        return qs
    from .models import Employee

    names, _ = downline_names_and_emails(user)
    known = set(Employee.objects.values_list("name", flat=True))
    return qs.filter(Q(**{f"{field}__in": names}) | ~Q(**{f"{field}__in": known}))


def scope_by_employee_fk(qs, user, fk_field, full_roles=EVERYTHING):
    """For a model whose "whose" field is a FK to Salesman or Employee (e.g.
    Target.employee -> Salesman, Dealer.ase -> Employee) — scoped by matching
    the linked row's *name* against the downline. Works for either target
    model since both have a `.name` field; matching by name rather than pk
    keeps this one helper usable for both without caring which it points at
    (and Salesman has no email to match on, so name is what's available)."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in full_roles:
        return qs
    from .models import Employee

    names, _ = downline_names_and_emails(user)
    known = set(Employee.objects.values_list("name", flat=True))
    return qs.filter(
        Q(**{f"{fk_field}__name__in": names})
        | Q(**{f"{fk_field}__isnull": True})
        | ~Q(**{f"{fk_field}__name__in": known})
    )


#: HR module data (salary, DOB, address, promotion/reward/punishment history)
#: is tighter than the general self+downline rule — a DSM does not get to
#: browse their downline's salaries just because sales data is scoped that
#: way. Only Manager and HR see anyone else's row.
HR_FULL_VISIBILITY = {"Manager", "HR"}


def scope_hr_self(qs, user):
    """For Employee itself: Manager/HR see everyone, everyone else sees only
    their own record."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in HR_FULL_VISIBILITY:
        return qs
    return qs.filter(pk=user.pk)


def scope_hr_related(qs, user, employee_field="employee"):
    """For PromotionHistory / EmployeeReward / EmployeePunishment: Manager/HR
    see everyone's; everyone else sees only rows about themselves."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in HR_FULL_VISIBILITY:
        return qs
    return qs.filter(**{employee_field: user.pk})


def scope_by_shop(qs, user, shop_field="shop", full_roles=EVERYTHING):
    """For models that only carry a shop *name* (Payment, Payout, CashbackTxn,
    OfferAccrual) — scoped indirectly through the Shop that name belongs to:
    visible if that Shop's assigned officer (Shop.srEmail) is the user or in
    their downline. A shop name with no matching Shop row, or a Shop with no
    srEmail / an srEmail that matches no known Employee, passes through
    unscoped — same "don't confidently hide what we can't confidently
    attribute" rule as everywhere else in this module."""
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.role in full_roles:
        return qs
    from .models import Employee, Shop

    _, emails = downline_names_and_emails(user)
    known = set(Employee.objects.exclude(email="").values_list("email", flat=True))
    visible_shops = set(
        Shop.objects.filter(Q(srEmail__in=emails) | ~Q(srEmail__in=known) | Q(srEmail="")).values_list(
            "name", flat=True
        )
    )
    known_shop_names = set(Shop.objects.values_list("name", flat=True))
    return qs.filter(Q(**{f"{shop_field}__in": visible_shops}) | ~Q(**{f"{shop_field}__in": known_shop_names}))
