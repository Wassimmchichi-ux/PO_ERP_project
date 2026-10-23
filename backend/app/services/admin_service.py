"""System administrator service functions."""
from __future__ import annotations

import datetime as dt
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions.base import ConflictException, NotFoundException, ValidationException
from app.models import (
    AuditLog,
    Contact,
    Customer,
    DeliveryMethod,
    FGPN,
    Launch,
    Material,
    MaterialType,
    ManufacturingReceiver,
    Project,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
    SupplierMaterialOrder,
    User,
)
from app.repositories.bom_repository import _get_system_user
from app.schemas.admin import (
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    ReferenceItemCreateRequest,
    ReferenceItemResponse,
    ReferenceItemUpdateRequest,
    ReferenceListName,
    ReferenceListsResponse,
)


def list_users(db: Session) -> AdminUserListResponse:
    users = db.execute(select(User).order_by(User.full_name)).scalars().all()
    items = [_to_user_response(db, user) for user in users]
    return AdminUserListResponse(items=items, total=len(items))


def create_user(db: Session, request: AdminUserCreateRequest) -> AdminUserResponse:
    registration_number = request.registration_number.strip()
    if _registration_exists(db, registration_number):
        raise ConflictException(f"User {registration_number} already exists.")

    user = User(
        full_name=request.full_name.strip(),
        registration_number=registration_number,
        password_hash=f"temporary:{request.temporary_password or 'ChangeMe!2026'}",
        role=request.role,
        status="ACTIVE",
        failed_login_count=0,
        is_locked=False,
        created_at=dt.datetime.now(),
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    _assign_projects(db, user.id, request.project_ids)
    _audit(db, "ADMIN_USER_CREATED", "User", None, f"{registration_number} created as {request.role}")
    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


def update_user(db: Session, user_id: uuid.UUID, request: AdminUserUpdateRequest) -> AdminUserResponse:
    user = _get_user(db, user_id)
    if request.registration_number is not None:
        registration_number = request.registration_number.strip()
        if _registration_exists(db, registration_number, excluding=user.id):
            raise ConflictException(f"User {registration_number} already exists.")
        user.registration_number = registration_number
    if request.full_name is not None:
        user.full_name = request.full_name.strip()
    if request.role is not None:
        user.role = request.role
    if request.status is not None:
        user.status = request.status
    if request.must_change_password is not None:
        user.must_change_password = request.must_change_password
    if request.project_ids is not None:
        _assign_projects(db, user.id, request.project_ids)
    _audit(db, "ADMIN_USER_UPDATED", "User", None, f"{user.registration_number} updated")
    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


def set_user_active(db: Session, user_id: uuid.UUID, active: bool) -> AdminUserResponse:
    user = _get_user(db, user_id)
    user.status = "ACTIVE" if active else "INACTIVE"
    _audit(db, "ADMIN_USER_ACTIVATED" if active else "ADMIN_USER_DEACTIVATED", "User", None, user.registration_number)
    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


def set_user_locked(db: Session, user_id: uuid.UUID, locked: bool) -> AdminUserResponse:
    user = _get_user(db, user_id)
    user.is_locked = locked
    user.locked_at = dt.datetime.now() if locked else None
    if not locked:
        user.failed_login_count = 0
    _audit(db, "ADMIN_USER_LOCKED" if locked else "ADMIN_USER_UNLOCKED", "User", None, user.registration_number)
    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


def force_password_reset(db: Session, user_id: uuid.UUID) -> AdminUserResponse:
    user = _get_user(db, user_id)
    user.must_change_password = True
    _audit(db, "ADMIN_PASSWORD_RESET_REQUIRED", "User", None, user.registration_number)
    db.commit()
    db.refresh(user)
    return _to_user_response(db, user)


def list_reference_items(db: Session) -> ReferenceListsResponse:
    items: list[ReferenceItemResponse] = []
    items.extend(_customer_items(db))
    items.extend(_contact_items(db))
    items.extend(_fgpn_items(db))
    items.extend(_receiver_items(db))
    items.extend(_delivery_method_items(db))
    items.extend(_material_type_items(db))
    items.extend(_supplier_items(db))
    return ReferenceListsResponse(items=items, total=len(items))


def create_reference_item(
    db: Session,
    list_name: ReferenceListName,
    request: ReferenceItemCreateRequest,
) -> ReferenceItemResponse:
    value = request.value.strip()
    now = dt.datetime.now()
    item: ReferenceItemResponse

    if list_name == "customers":
        code = (request.code or _slug(value)).strip()
        if db.execute(select(Customer).where(Customer.customer_code == code)).scalar_one_or_none():
            raise ConflictException(f"Customer code {code} already exists.")
        model = Customer(customer_code=code, name=value, status="Active", created_at=now, updated_at=now)
        db.add(model)
        db.flush()
        item = _customer_response(db, model)
    elif list_name == "contacts":
        customer_id = request.customer_id or _customer_id_from_detail(db, request.detail)
        model = Contact(
            customer_id=customer_id,
            name=value,
            email=None,
            phone=None,
            status="Active",
            created_at=now,
            updated_at=now,
        )
        db.add(model)
        db.flush()
        item = _contact_response(db, model)
    elif list_name == "manufacturing-receivers":
        model = ManufacturingReceiver(name=value, status="Active")
        db.add(model)
        db.flush()
        item = _receiver_response(db, model)
    elif list_name == "delivery-methods":
        model = DeliveryMethod(name=value, status="Active")
        db.add(model)
        db.flush()
        item = _delivery_method_response(db, model)
    elif list_name == "material-types":
        model = MaterialType(name=value, unit=(request.unit or request.detail or "pcs").strip(), status="Active")
        db.add(model)
        db.flush()
        item = _material_type_response(db, model)
    elif list_name == "finished-goods-part-numbers":
        project_id = _project_id_from_detail(db, request.detail)
        model = FGPN(
            project_id=project_id,
            fgpn_code=value,
            description=request.detail,
            unit_price=0,
            status="Active",
            created_at=now,
            updated_at=now,
        )
        db.add(model)
        db.flush()
        item = _fgpn_response(db, model)
    elif list_name == "suppliers":
        reference = (request.code or request.detail or "").strip()
        if not reference:
            raise ValidationException("Supplier reference is required.")
        if db.scalar(select(Supplier.supplier_id).where(Supplier.supplier_reference == reference)):
            raise ConflictException(f"Supplier reference {reference} already exists.")
        model = Supplier(
            supplier_reference=reference,
            full_name=value,
            status="Active",
            created_at=now,
            updated_at=now,
        )
        db.add(model)
        db.flush()
        item = _supplier_response(db, model)
    else:
        raise ValidationException(f"Unsupported reference list {list_name}.")

    _audit(db, "ADMIN_REFERENCE_CREATED", item.list, _numeric_id(item.id), item.value)
    db.commit()
    return item


def update_reference_item(
    db: Session,
    list_name: ReferenceListName,
    item_id: int,
    request: ReferenceItemUpdateRequest,
) -> ReferenceItemResponse:
    if list_name == "customers":
        model = _get_or_404(db, Customer, item_id)
        if request.value is not None:
            model.name = request.value.strip()
        if request.code is not None:
            model.customer_code = request.code.strip()
        if request.active is not None:
            model.status = _status(request.active)
        model.updated_at = dt.datetime.now()
        item = _customer_response(db, model)
    elif list_name == "contacts":
        model = _get_or_404(db, Contact, item_id)
        if request.value is not None:
            model.name = request.value.strip()
        if request.customer_id is not None:
            model.customer_id = request.customer_id
        if request.active is not None:
            model.status = _status(request.active)
        model.updated_at = dt.datetime.now()
        item = _contact_response(db, model)
    elif list_name == "manufacturing-receivers":
        model = _get_or_404(db, ManufacturingReceiver, item_id)
        if request.value is not None:
            model.name = request.value.strip()
        if request.active is not None:
            model.status = _status(request.active)
        item = _receiver_response(db, model)
    elif list_name == "delivery-methods":
        model = _get_or_404(db, DeliveryMethod, item_id)
        if request.value is not None:
            model.name = request.value.strip()
        if request.active is not None:
            model.status = _status(request.active)
        item = _delivery_method_response(db, model)
    elif list_name == "material-types":
        model = _get_or_404(db, MaterialType, item_id)
        if request.value is not None:
            model.name = request.value.strip()
        if request.unit is not None or request.detail is not None:
            model.unit = (request.unit or request.detail or model.unit).strip()
        if request.active is not None:
            model.status = _status(request.active)
        item = _material_type_response(db, model)
    elif list_name == "finished-goods-part-numbers":
        model = _get_or_404(db, FGPN, item_id)
        if request.value is not None:
            model.fgpn_code = request.value.strip()
        if request.detail is not None:
            model.description = request.detail.strip()
        if request.active is not None:
            model.status = _status(request.active)
        model.updated_at = dt.datetime.now()
        item = _fgpn_response(db, model)
    elif list_name == "suppliers":
        model = _get_or_404(db, Supplier, item_id)
        if request.value is not None:
            model.full_name = request.value.strip()
        if request.code is not None or request.detail is not None:
            reference = (request.code or request.detail or "").strip()
            if not reference:
                raise ValidationException("Supplier reference is required.")
            duplicate = db.scalar(
                select(Supplier.supplier_id)
                .where(Supplier.supplier_reference == reference)
                .where(Supplier.supplier_id != model.supplier_id)
            )
            if duplicate is not None:
                raise ConflictException(f"Supplier reference {reference} already exists.")
            model.supplier_reference = reference
        if request.active is not None:
            model.status = _status(request.active)
        model.updated_at = dt.datetime.now()
        item = _supplier_response(db, model)
    else:
        raise ValidationException(f"Unsupported reference list {list_name}.")

    _audit(db, "ADMIN_REFERENCE_UPDATED", item.list, item_id, item.value)
    db.commit()
    return item


def _to_user_response(db: Session, user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        full_name=user.full_name,
        registration_number=user.registration_number,
        role=user.role,
        status=user.status,
        is_locked=user.is_locked,
        must_change_password=user.must_change_password,
        failed_login_count=user.failed_login_count,
        locked_at=user.locked_at,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        project_ids=[
            row[0]
            for row in db.execute(
                select(Project.project_id).where(Project.launch_engineer_user_id == user.id).order_by(Project.project_code)
            ).all()
        ],
    )


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundException(f"User {user_id} not found.")
    return user


def _registration_exists(db: Session, registration_number: str, excluding: uuid.UUID | None = None) -> bool:
    query = select(User).where(User.registration_number == registration_number)
    if excluding:
        query = query.where(User.id != excluding)
    return db.execute(query).scalar_one_or_none() is not None


def _assign_projects(db: Session, user_id: uuid.UUID, project_ids: list[int]) -> None:
    if not project_ids:
        return
    projects = db.execute(select(Project).where(Project.project_id.in_(project_ids))).scalars().all()
    if len(projects) != len(set(project_ids)):
        found = {project.project_id for project in projects}
        missing = sorted(set(project_ids) - found)
        raise NotFoundException(f"Project(s) not found: {missing}")
    for project in projects:
        project.launch_engineer_user_id = user_id
        project.updated_at = dt.datetime.now()


def _customer_items(db: Session) -> list[ReferenceItemResponse]:
    return [_customer_response(db, item) for item in db.execute(select(Customer).order_by(Customer.name)).scalars()]


def _contact_items(db: Session) -> list[ReferenceItemResponse]:
    return [_contact_response(db, item) for item in db.execute(select(Contact).order_by(Contact.name)).scalars()]


def _fgpn_items(db: Session) -> list[ReferenceItemResponse]:
    return [_fgpn_response(db, item) for item in db.execute(select(FGPN).order_by(FGPN.fgpn_code)).scalars()]


def _receiver_items(db: Session) -> list[ReferenceItemResponse]:
    return [
        _receiver_response(db, item)
        for item in db.execute(select(ManufacturingReceiver).order_by(ManufacturingReceiver.name)).scalars()
    ]


def _delivery_method_items(db: Session) -> list[ReferenceItemResponse]:
    return [
        _delivery_method_response(db, item)
        for item in db.execute(select(DeliveryMethod).order_by(DeliveryMethod.name)).scalars()
    ]


def _material_type_items(db: Session) -> list[ReferenceItemResponse]:
    return [_material_type_response(db, item) for item in db.execute(select(MaterialType).order_by(MaterialType.name)).scalars()]


def _supplier_items(db: Session) -> list[ReferenceItemResponse]:
    return [
        _supplier_response(db, item)
        for item in db.execute(select(Supplier).order_by(Supplier.full_name)).scalars()
    ]


def _customer_response(db: Session, item: Customer) -> ReferenceItemResponse:
    return ReferenceItemResponse(
        id=f"customers:{item.customer_id}",
        list="JIT Customers",
        value=item.name,
        detail=item.customer_code,
        active=_is_active(item.status),
        linked_records=_count(db, PurchaseOrder.customer_id == item.customer_id),
    )


def _contact_response(db: Session, item: Contact) -> ReferenceItemResponse:
    customer = db.get(Customer, item.customer_id)
    return ReferenceItemResponse(
        id=f"contacts:{item.contact_id}",
        list="Contact Names",
        value=item.name,
        detail=customer.name if customer else None,
        active=_is_active(item.status),
        linked_records=_count(db, PurchaseOrder.contact_id == item.contact_id),
    )


def _fgpn_response(db: Session, item: FGPN) -> ReferenceItemResponse:
    project = db.get(Project, item.project_id)
    return ReferenceItemResponse(
        id=f"finished-goods-part-numbers:{item.fgpn_id}",
        list="Finished Goods Part Numbers",
        value=item.fgpn_code,
        detail=project.project_code if project else item.description,
        active=_is_active(item.status),
        linked_records=_count(db, PurchaseOrderLine.fgpn_id == item.fgpn_id),
    )


def _receiver_response(db: Session, item: ManufacturingReceiver) -> ReferenceItemResponse:
    return ReferenceItemResponse(
        id=f"manufacturing-receivers:{item.receiver_id}",
        list="Manufacturing Receivers",
        value=item.name,
        detail=None,
        active=_is_active(item.status),
        linked_records=_count(db, Launch.receiver_id == item.receiver_id),
    )


def _delivery_method_response(db: Session, item: DeliveryMethod) -> ReferenceItemResponse:
    linked = _count(db, PurchaseOrderLine.delivery_method_id == item.delivery_method_id) + _count(
        db,
        Launch.delivery_method_id == item.delivery_method_id,
    )
    return ReferenceItemResponse(
        id=f"delivery-methods:{item.delivery_method_id}",
        list="Delivery Methods",
        value=item.name,
        detail=None,
        active=_is_active(item.status),
        linked_records=linked,
    )


def _material_type_response(db: Session, item: MaterialType) -> ReferenceItemResponse:
    return ReferenceItemResponse(
        id=f"material-types:{item.material_type_id}",
        list="Material Types",
        value=item.name,
        detail=item.unit,
        active=_is_active(item.status),
        linked_records=_count(db, Material.material_type_id == item.material_type_id),
    )


def _supplier_response(db: Session, item: Supplier) -> ReferenceItemResponse:
    return ReferenceItemResponse(
        id=f"suppliers:{item.supplier_id}",
        list="Suppliers",
        value=item.full_name,
        detail=item.supplier_reference,
        active=_is_active(item.status),
        linked_records=_count(db, SupplierMaterialOrder.supplier_id == item.supplier_id),
    )


def _get_or_404(db: Session, model: type, item_id: int):
    item = db.get(model, item_id)
    if item is None:
        raise NotFoundException(f"{model.__name__} {item_id} not found.")
    return item


def _count(db: Session, criterion) -> int:
    return db.execute(select(func.count()).where(criterion)).scalar_one()


def _status(active: bool) -> str:
    return "Active" if active else "Inactive"


def _is_active(value: str) -> bool:
    return value.upper() == "ACTIVE" or value == "Active"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.upper()).strip("-")
    return (slug or "REF")[:50]


def _customer_id_from_detail(db: Session, detail: str | None) -> int:
    if detail:
        customer = db.execute(select(Customer).where(Customer.name == detail.strip())).scalar_one_or_none()
        if customer:
            return customer.customer_id
    customer_id = db.execute(select(Customer.customer_id).order_by(Customer.customer_id)).scalar_one_or_none()
    if customer_id is None:
        raise ValidationException("Create a customer before adding contact names.")
    return customer_id


def _project_id_from_detail(db: Session, detail: str | None) -> int:
    if detail:
        project = db.execute(select(Project).where(Project.project_code == detail.strip())).scalar_one_or_none()
        if project:
            return project.project_id
    project_id = db.execute(select(Project.project_id).order_by(Project.project_id)).scalar_one_or_none()
    if project_id is None:
        raise ValidationException("Create a project before adding finished goods part numbers.")
    return project_id


def _numeric_id(reference_id: str) -> int | None:
    try:
        return int(reference_id.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _audit(db: Session, action: str, entity_type: str, entity_id: int | None, details: str) -> None:
    db.add(
        AuditLog(
            user_id=_get_system_user(db),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=dt.datetime.now(),
            reason="System administrator workflow",
            details=details,
        )
    )
