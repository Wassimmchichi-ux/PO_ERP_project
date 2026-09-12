from typing import Any, Optional
import datetime
import decimal
import enum
import uuid

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKeyConstraint, Identity, Index, Integer, JSON, Numeric, PrimaryKeyConstraint, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
# Import all model files so Alembic sees every table

class Base(DeclarativeBase):
    pass


class FailureReason(str, enum.Enum):
    NONE = 'NONE'
    UNKNOWN_USER = 'UNKNOWN_USER'
    INVALID_PASSWORD = 'INVALID_PASSWORD'
    ACCOUNT_LOCKED = 'ACCOUNT_LOCKED'
    ACCOUNT_INACTIVE = 'ACCOUNT_INACTIVE'


class RecordStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'


class RoleCode(str, enum.Enum):
    ADMIN = 'ADMIN'
    PLANT_MANAGER = 'PLANT_MANAGER'
    LAUNCH_ENGINEER = 'LAUNCH_ENGINEER'
    LAUNCH_MANAGER = 'LAUNCH_MANAGER'
    WAREHOUSE_PERSONNEL = 'WAREHOUSE_Personnel'
    WAREHOUSE_TEAM_LEADER = 'WAREHOUSE_TEAM_LEADER'
    MANUFACTURING_OPERATOR = 'MANUFACTURING_OPERATOR'


class Customer(Base):
    __tablename__ = 'Customer'
    __table_args__ = (
        PrimaryKeyConstraint('customer_id', name='Customer_pkey'),
        UniqueConstraint('customer_code', name='Customer_customer_code_key')
    )

    customer_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    customer_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    PurchaseOrder: Mapped[list['PurchaseOrder']] = relationship('PurchaseOrder', back_populates='customer')
    Contact: Mapped[list['Contact']] = relationship('Contact', back_populates='customer')


class DeliveryMethod(Base):
    __tablename__ = 'DeliveryMethod'
    __table_args__ = (
        PrimaryKeyConstraint('delivery_method_id', name='DeliveryMethod_pkey'),
        UniqueConstraint('name', name='DeliveryMethod_name_key')
    )

    delivery_method_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')

    Launch: Mapped[list['Launch']] = relationship('Launch', back_populates='delivery_method')
    PurchaseOrderLine: Mapped[list['PurchaseOrderLine']] = relationship('PurchaseOrderLine', back_populates='delivery_method')


class ManufacturingReceiver(Base):
    __tablename__ = 'ManufacturingReceiver'
    __table_args__ = (
        PrimaryKeyConstraint('receiver_id', name='ManufacturingReceiver_pkey'),
    )

    receiver_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')

    Launch: Mapped[list['Launch']] = relationship('Launch', back_populates='receiver')


class MaterialType(Base):
    __tablename__ = 'MaterialType'
    __table_args__ = (
        PrimaryKeyConstraint('material_type_id', name='MaterialType_pkey'),
        UniqueConstraint('name', name='MaterialType_name_key')
    )

    material_type_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='c, m, s')
    unit: Mapped[str] = mapped_column(String(10), nullable=False, comment='m, kg, pcs, etc.')
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')

    Material: Mapped[list['Material']] = relationship('Material', back_populates='material_type')


class PurchaseOrder(Base):
    __tablename__ = 'PurchaseOrder'
    __table_args__ = (
        ForeignKeyConstraint(['contact_id'], ['Contact.contact_id'], deferrable=True, name='PurchaseOrder_contact_id_fkey'),
        ForeignKeyConstraint(['current_version_id'], ['PurchaseOrderVersion.po_version_id'], deferrable=True, name='PurchaseOrder_current_version_id_fkey'),
        ForeignKeyConstraint(['customer_id'], ['Customer.customer_id'], deferrable=True, name='PurchaseOrder_customer_id_fkey'),
        PrimaryKeyConstraint('po_id', name='PurchaseOrder_pkey'),
        UniqueConstraint('po_number', name='PurchaseOrder_po_number_key')
    )

    po_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(10), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    current_version_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_status: Mapped[str] = mapped_column(String(30), nullable=False, comment='Unplanned, In Progress, Done, Packaged, Delivered')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    contact: Mapped['Contact'] = relationship('Contact', back_populates='PurchaseOrder_')
    current_version: Mapped['PurchaseOrderVersion'] = relationship('PurchaseOrderVersion', foreign_keys=[current_version_id], back_populates='PurchaseOrder_current_version', post_update=True)
    customer: Mapped['Customer'] = relationship('Customer', back_populates='PurchaseOrder')
    PurchaseOrderVersion_po: Mapped[list['PurchaseOrderVersion']] = relationship('PurchaseOrderVersion', foreign_keys='[PurchaseOrderVersion.po_id]', back_populates='po')
    POStatusHistory: Mapped[list['POStatusHistory']] = relationship('POStatusHistory', back_populates='po')
    LaunchPO: Mapped[list['LaunchPO']] = relationship('LaunchPO', back_populates='po')


class PurchaseOrderVersion(Base):
    __tablename__ = 'PurchaseOrderVersion'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], deferrable=True, name='PurchaseOrderVersion_created_by_fkey'),
        ForeignKeyConstraint(['document_id'], ['Document.document_id'], deferrable=True, name='PurchaseOrderVersion_document_id_fkey'),
        ForeignKeyConstraint(['po_id'], ['PurchaseOrder.po_id'], deferrable=True, name='PurchaseOrderVersion_po_id_fkey'),
        PrimaryKeyConstraint('po_version_id', name='PurchaseOrderVersion_pkey'),
        Index('PurchaseOrderVersion_po_id_version_number_idx', 'po_id', 'version_number', unique=True)
    )

    po_version_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    document_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    car_model: Mapped[Optional[str]] = mapped_column(String(100))
    engineering_phase_level: Mapped[Optional[str]] = mapped_column(String(50))
    po_level: Mapped[Optional[str]] = mapped_column(String(6))
    reason_of_purchase_order: Mapped[Optional[str]] = mapped_column(String(255))
    change_reason: Mapped[Optional[str]] = mapped_column(String(255))

    PurchaseOrder_current_version: Mapped[list['PurchaseOrder']] = relationship('PurchaseOrder', foreign_keys='[PurchaseOrder.current_version_id]', back_populates='current_version')
    user: Mapped['User'] = relationship('User', back_populates='PurchaseOrderVersion_')
    document: Mapped['Document'] = relationship('Document', back_populates='PurchaseOrderVersion_')
    po: Mapped['PurchaseOrder'] = relationship('PurchaseOrder', foreign_keys=[po_id], back_populates='PurchaseOrderVersion_po')
    PurchaseOrderVersionChange: Mapped[list['PurchaseOrderVersionChange']] = relationship('PurchaseOrderVersionChange', back_populates='po_version')
    PurchaseOrderLine: Mapped[list['PurchaseOrderLine']] = relationship('PurchaseOrderLine', back_populates='po_version')


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('registration_number', name='users_registration_number_key'),
        {'comment': 'One role per user. Accounts are deactivated, never deleted, so '
                'historical actions keep their actor.'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleCode] = mapped_column(Enum(RoleCode, values_callable=lambda cls: [member.value for member in cls], name='role_code'), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(Enum(RecordStatus, values_callable=lambda cls: [member.value for member in cls], name='record_status'), nullable=False, server_default=text("'ACTIVE'::record_status"))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'))
    locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    PurchaseOrderVersion_: Mapped[list['PurchaseOrderVersion']] = relationship('PurchaseOrderVersion', back_populates='user')
    AuditLog: Mapped[list['AuditLog']] = relationship('AuditLog', back_populates='user')
    Document: Mapped[list['Document']] = relationship('Document', back_populates='user')
    Project: Mapped[list['Project']] = relationship('Project', back_populates='launch_engineer_user')
    login_events: Mapped[list['LoginEvents']] = relationship('LoginEvents', back_populates='user')
    CorrectionEvent: Mapped[list['CorrectionEvent']] = relationship('CorrectionEvent', back_populates='user')
    POStatusHistory: Mapped[list['POStatusHistory']] = relationship('POStatusHistory', back_populates='user')
    Simulation: Mapped[list['Simulation']] = relationship('Simulation', foreign_keys='[Simulation.created_by]', back_populates='user')
    Simulation_stock_owner: Mapped[list['Simulation']] = relationship('Simulation', foreign_keys='[Simulation.stock_owner_user_id]', back_populates='stock_owner')
    BOM: Mapped[list['BOM']] = relationship('BOM', back_populates='user')
    FGPNPriceHistory: Mapped[list['FGPNPriceHistory']] = relationship('FGPNPriceHistory', back_populates='user')
    Launch_completed_by: Mapped[list['Launch']] = relationship('Launch', foreign_keys='[Launch.completed_by]', back_populates='completed_by_user')
    Launch_verified_by: Mapped[list['Launch']] = relationship('Launch', foreign_keys='[Launch.verified_by]', back_populates='verified_by_user')
    LaunchVerification: Mapped[list['LaunchVerification']] = relationship('LaunchVerification', back_populates='user')


class AuditLog(Base):
    __tablename__ = 'AuditLog'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], deferrable=True, name='AuditLog_user_id_fkey'),
        PrimaryKeyConstraint('audit_id', name='AuditLog_pkey')
    )

    audit_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    details: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped['User'] = relationship('User', back_populates='AuditLog')
    CorrectionEvent: Mapped[list['CorrectionEvent']] = relationship('CorrectionEvent', back_populates='audit')
    POStatusHistory: Mapped[list['POStatusHistory']] = relationship('POStatusHistory', back_populates='audit')
    BOM: Mapped[list['BOM']] = relationship('BOM', back_populates='audit')
    FGPNPriceHistory: Mapped[list['FGPNPriceHistory']] = relationship('FGPNPriceHistory', back_populates='audit')


class Contact(Base):
    __tablename__ = 'Contact'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['Customer.customer_id'], deferrable=True, name='Contact_customer_id_fkey'),
        PrimaryKeyConstraint('contact_id', name='Contact_pkey')
    )

    contact_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(150))
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    PurchaseOrder_: Mapped[list['PurchaseOrder']] = relationship('PurchaseOrder', back_populates='contact')
    customer: Mapped['Customer'] = relationship('Customer', back_populates='Contact')


class Document(Base):
    __tablename__ = 'Document'
    __table_args__ = (
        ForeignKeyConstraint(['uploaded_by'], ['users.id'], deferrable=True, name='Document_uploaded_by_fkey'),
        PrimaryKeyConstraint('document_id', name='Document_pkey')
    )

    document_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, comment='PO, BOM, CUTMAN_REPORT, LAUNCH_SUMMARY, SIGNED_HANDOVER, MTG_MINUTES, OTHER')
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[Optional[int]] = mapped_column(Integer)

    PurchaseOrderVersion_: Mapped[list['PurchaseOrderVersion']] = relationship('PurchaseOrderVersion', back_populates='document')
    user: Mapped['User'] = relationship('User', back_populates='Document')
    Simulation: Mapped[list['Simulation']] = relationship('Simulation', back_populates='mtg_minutes_document')
    BOM: Mapped[list['BOM']] = relationship('BOM', back_populates='document')
    Launch: Mapped[list['Launch']] = relationship('Launch', back_populates='verification_document')
    StockIssueHandover: Mapped[list['StockIssueHandover']] = relationship('StockIssueHandover', back_populates='signed_document')
    CuttingConsumption: Mapped[list['CuttingConsumption']] = relationship('CuttingConsumption', back_populates='cutman_document')
    LaunchVerification_engineer_document: Mapped[list['LaunchVerification']] = relationship('LaunchVerification', foreign_keys='[LaunchVerification.engineer_document_id]', back_populates='engineer_document')
    LaunchVerification_summary_document: Mapped[list['LaunchVerification']] = relationship('LaunchVerification', foreign_keys='[LaunchVerification.summary_document_id]', back_populates='summary_document')


class Material(Base):
    __tablename__ = 'Material'
    __table_args__ = (
        ForeignKeyConstraint(['material_type_id'], ['MaterialType.material_type_id'], deferrable=True, name='Material_material_type_id_fkey'),
        PrimaryKeyConstraint('id', name='Material_pkey'),
        UniqueConstraint('material_part_number', name='Material_material_part_number_key')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String(50), nullable=False)
    material_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    material_part_number: Mapped[Optional[str]] = mapped_column(String(50))
    critical_threshold: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))

    material_type: Mapped['MaterialType'] = relationship('MaterialType', back_populates='Material')
    BOMLine: Mapped[list['BOMLine']] = relationship('BOMLine', back_populates='Material_')
    CuttingConsumption: Mapped[list['CuttingConsumption']] = relationship('CuttingConsumption', back_populates='Material_')


class Project(Base):
    __tablename__ = 'Project'
    __table_args__ = (
        ForeignKeyConstraint(['launch_engineer_user_id'], ['users.id'], deferrable=True, name='Project_launch_engineer_user_id_fkey'),
        PrimaryKeyConstraint('project_id', name='Project_pkey'),
        UniqueConstraint('project_code', name='Project_project_code_key')
    )

    project_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    launch_engineer_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    launch_engineer_user: Mapped['User'] = relationship('User', back_populates='Project')
    FGPN: Mapped[list['FGPN']] = relationship('FGPN', back_populates='project')


class PurchaseOrderVersionChange(Base):
    __tablename__ = 'PurchaseOrderVersionChange'
    __table_args__ = (
        ForeignKeyConstraint(['po_version_id'], ['PurchaseOrderVersion.po_version_id'], deferrable=True, name='PurchaseOrderVersionChange_po_version_id_fkey'),
        PrimaryKeyConstraint('change_id', name='PurchaseOrderVersionChange_pkey')
    )

    change_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    po_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, comment='PO_HEADER, PO_LINE')
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)

    po_version: Mapped['PurchaseOrderVersion'] = relationship('PurchaseOrderVersion', back_populates='PurchaseOrderVersionChange')


class LoginEvents(Base):
    __tablename__ = 'login_events'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], deferrable=True, name='login_events_user_id_fkey'),
        PrimaryKeyConstraint('id', name='login_events_pkey'),
        Index('login_events_attempted_rn_occurred_at_idx', 'attempted_rn', 'occurred_at'),
        {'comment': 'Stores successful and failed attempts, including attempts for an '
                'unknown username.'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    attempted_rn: Mapped[str] = mapped_column(String(80), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[FailureReason] = mapped_column(Enum(FailureReason, values_callable=lambda cls: [member.value for member in cls], name='failure_reason'), nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    user: Mapped['User'] = relationship('User', back_populates='login_events')


class CorrectionEvent(Base):
    __tablename__ = 'CorrectionEvent'
    __table_args__ = (
        ForeignKeyConstraint(['audit_id'], ['AuditLog.audit_id'], deferrable=True, name='CorrectionEvent_audit_id_fkey'),
        ForeignKeyConstraint(['corrected_by'], ['users.id'], deferrable=True, name='CorrectionEvent_corrected_by_fkey'),
        PrimaryKeyConstraint('correction_id', name='CorrectionEvent_pkey')
    )

    correction_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, comment='PO, PO_LINE')
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    corrected_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    corrected_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_value: Mapped[Optional[str]] = mapped_column(Text)
    corrected_value: Mapped[Optional[str]] = mapped_column(Text)

    audit: Mapped['AuditLog'] = relationship('AuditLog', back_populates='CorrectionEvent')
    user: Mapped['User'] = relationship('User', back_populates='CorrectionEvent')


class ParsedPurchaseOrder(Base):
    __tablename__ = 'ParsedPurchaseOrder'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], deferrable=True, name='ParsedPurchaseOrder_created_by_fkey'),
        ForeignKeyConstraint(['document_id'], ['Document.document_id'], deferrable=True, name='ParsedPurchaseOrder_document_id_fkey'),
        ForeignKeyConstraint(['validated_po_id'], ['PurchaseOrder.po_id'], deferrable=True, name='ParsedPurchaseOrder_validated_po_id_fkey'),
        PrimaryKeyConstraint('parsed_po_id', name='ParsedPurchaseOrder_pkey')
    )

    parsed_po_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'PARSED'::character varying"), comment='PARSED, CORRECTED, VALIDATED, IMPORTED, REJECTED')
    parsed_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(Integer)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255))
    parser_name: Mapped[Optional[str]] = mapped_column(String(100))
    parser_version: Mapped[Optional[str]] = mapped_column(String(50))
    validated_po_id: Mapped[Optional[int]] = mapped_column(Integer)

    document: Mapped[Optional['Document']] = relationship('Document')
    creator: Mapped['User'] = relationship('User')
    validated_purchase_order: Mapped[Optional['PurchaseOrder']] = relationship('PurchaseOrder')
    corrections: Mapped[list['ParsedPurchaseOrderCorrection']] = relationship('ParsedPurchaseOrderCorrection', back_populates='parsed_purchase_order')


class ParsedPurchaseOrderCorrection(Base):
    __tablename__ = 'ParsedPurchaseOrderCorrection'
    __table_args__ = (
        ForeignKeyConstraint(['corrected_by'], ['users.id'], deferrable=True, name='ParsedPurchaseOrderCorrection_corrected_by_fkey'),
        ForeignKeyConstraint(['parsed_po_id'], ['ParsedPurchaseOrder.parsed_po_id'], deferrable=True, name='ParsedPurchaseOrderCorrection_parsed_po_id_fkey'),
        PrimaryKeyConstraint('correction_id', name='ParsedPurchaseOrderCorrection_pkey'),
        Index('ParsedPurchaseOrderCorrection_parsed_po_id_field_path_idx', 'parsed_po_id', 'field_path', unique=True)
    )

    correction_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    parsed_po_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_path: Mapped[str] = mapped_column(String(255), nullable=False, comment='Header field or nested path like lines[0].quantity')
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    corrected_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    corrected_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    original_value: Mapped[Optional[Any]] = mapped_column(JSON)
    corrected_value: Mapped[Optional[Any]] = mapped_column(JSON)

    parsed_purchase_order: Mapped['ParsedPurchaseOrder'] = relationship('ParsedPurchaseOrder', back_populates='corrections')
    corrector: Mapped['User'] = relationship('User')


class FGPN(Base):
    __tablename__ = 'FGPN'
    __table_args__ = (
        ForeignKeyConstraint(['project_id'], ['Project.project_id'], deferrable=True, name='FGPN_project_id_fkey'),
        PrimaryKeyConstraint('fgpn_id', name='FGPN_pkey'),
        Index('FGPN_project_id_fgpn_code_idx', 'project_id', 'fgpn_code', unique=True)
    )

    fgpn_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fgpn_code: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Active'::character varying"), comment='Active, Inactive')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    trim_style: Mapped[Optional[str]] = mapped_column(String(255))

    project: Mapped['Project'] = relationship('Project', back_populates='FGPN')
    BOM: Mapped[list['BOM']] = relationship('BOM', back_populates='fgpn')
    FGPNPriceHistory: Mapped[list['FGPNPriceHistory']] = relationship('FGPNPriceHistory', back_populates='fgpn')
    PurchaseOrderLine: Mapped[list['PurchaseOrderLine']] = relationship('PurchaseOrderLine', back_populates='fgpn')
    LaunchFGPN: Mapped[list['LaunchFGPN']] = relationship('LaunchFGPN', back_populates='fgpn')


class POStatusHistory(Base):
    __tablename__ = 'POStatusHistory'
    __table_args__ = (
        ForeignKeyConstraint(['audit_id'], ['AuditLog.audit_id'], deferrable=True, name='POStatusHistory_audit_id_fkey'),
        ForeignKeyConstraint(['changed_by'], ['users.id'], deferrable=True, name='POStatusHistory_changed_by_fkey'),
        ForeignKeyConstraint(['po_id'], ['PurchaseOrder.po_id'], deferrable=True, name='POStatusHistory_po_id_fkey'),
        PrimaryKeyConstraint('status_history_id', name='POStatusHistory_pkey')
    )

    status_history_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(Integer, nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(30))
    reason: Mapped[Optional[str]] = mapped_column(String(255))

    audit: Mapped['AuditLog'] = relationship('AuditLog', back_populates='POStatusHistory')
    user: Mapped['User'] = relationship('User', back_populates='POStatusHistory')
    po: Mapped['PurchaseOrder'] = relationship('PurchaseOrder', back_populates='POStatusHistory')


class Simulation(Base):
    __tablename__ = 'Simulation'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], deferrable=True, name='Simulation_created_by_fkey'),
        ForeignKeyConstraint(['mtg_minutes_document_id'], ['Document.document_id'], deferrable=True, name='Simulation_mtg_minutes_document_id_fkey'),
        ForeignKeyConstraint(['stock_owner_user_id'], ['users.id'], deferrable=True, name='Simulation_stock_owner_user_id_fkey'),
        PrimaryKeyConstraint('simulation_id', name='Simulation_pkey')
    )

    simulation_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    simulation_mode: Mapped[str] = mapped_column(String(30), nullable=False, comment='CURRENT_STOCK, INCLUDING_IN_TRANSIT')
    stock_scope_mode: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'ALL'::character varying"), comment='ALL, OWNED_ONLY')
    include_global_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='When OWNED_ONLY, include global stock units with no affected owner.')
    target_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    safety_coefficient: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text('2'))
    is_feasible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mtg_minutes_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    shortfall_json: Mapped[Optional[str]] = mapped_column(Text)
    stock_owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    user: Mapped['User'] = relationship('User', foreign_keys=[created_by], back_populates='Simulation')
    stock_owner: Mapped[Optional['User']] = relationship('User', foreign_keys=[stock_owner_user_id], back_populates='Simulation_stock_owner')
    mtg_minutes_document: Mapped['Document'] = relationship('Document', back_populates='Simulation')
    StockAllocation: Mapped[list['StockAllocation']] = relationship('StockAllocation', back_populates='simulation')
    StockIssueHandover: Mapped[list['StockIssueHandover']] = relationship('StockIssueHandover', back_populates='simulation')


class BOM(Base):
    __tablename__ = 'BOM'
    __table_args__ = (
        ForeignKeyConstraint(['audit_id'], ['AuditLog.audit_id'], deferrable=True, name='BOM_audit_id_fkey'),
        ForeignKeyConstraint(['created_by'], ['users.id'], deferrable=True, name='BOM_created_by_fkey'),
        ForeignKeyConstraint(['document_id'], ['Document.document_id'], deferrable=True, name='BOM_document_id_fkey'),
        ForeignKeyConstraint(['fgpn_id'], ['FGPN.fgpn_id'], deferrable=True, name='BOM_fgpn_id_fkey'),
        PrimaryKeyConstraint('bom_id', name='BOM_pkey')
    )

    bom_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    fgpn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    audit: Mapped['AuditLog'] = relationship('AuditLog', back_populates='BOM')
    user: Mapped['User'] = relationship('User', back_populates='BOM')
    document: Mapped['Document'] = relationship('Document', back_populates='BOM')
    fgpn: Mapped['FGPN'] = relationship('FGPN', back_populates='BOM')
    BOMLine: Mapped[list['BOMLine']] = relationship('BOMLine', back_populates='bom')
    @property
    def material_lines(self) -> list['BOMLine']:
        return self.BOMLine

class FGPNPriceHistory(Base):
    __tablename__ = 'FGPNPriceHistory'
    __table_args__ = (
        ForeignKeyConstraint(['audit_id'], ['AuditLog.audit_id'], deferrable=True, name='FGPNPriceHistory_audit_id_fkey'),
        ForeignKeyConstraint(['changed_by'], ['users.id'], deferrable=True, name='FGPNPriceHistory_changed_by_fkey'),
        ForeignKeyConstraint(['fgpn_id'], ['FGPN.fgpn_id'], deferrable=True, name='FGPNPriceHistory_fgpn_id_fkey'),
        PrimaryKeyConstraint('price_history_id', name='FGPNPriceHistory_pkey')
    )

    price_history_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    fgpn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    new_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    effective_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    audit: Mapped['AuditLog'] = relationship('AuditLog', back_populates='FGPNPriceHistory')
    user: Mapped['User'] = relationship('User', back_populates='FGPNPriceHistory')
    fgpn: Mapped['FGPN'] = relationship('FGPN', back_populates='FGPNPriceHistory')


class Launch(Base):
    __tablename__ = 'Launch'
    __table_args__ = (
        ForeignKeyConstraint(['completed_by'], ['users.id'], deferrable=True, name='Launch_completed_by_fkey'),
        ForeignKeyConstraint(['delivery_method_id'], ['DeliveryMethod.delivery_method_id'], deferrable=True, name='Launch_delivery_method_id_fkey'),
        ForeignKeyConstraint(['receiver_id'], ['ManufacturingReceiver.receiver_id'], deferrable=True, name='Launch_receiver_id_fkey'),
        ForeignKeyConstraint(['simulation_id'], ['Simulation.simulation_id'], deferrable=True, name='Launch_simulation_id_fkey'),
        ForeignKeyConstraint(['verification_document_id'], ['Document.document_id'], deferrable=True, name='Launch_verification_document_id_fkey'),
        ForeignKeyConstraint(['verified_by'], ['users.id'], deferrable=True, name='Launch_verified_by_fkey'),
        UniqueConstraint('simulation_id', name='Launch_simulation_id_key'),
        PrimaryKeyConstraint('launch_id', name='Launch_pkey')
    )

    launch_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    delivery_method_id: Mapped[int] = mapped_column(Integer, nullable=False)
    receiver_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, comment='PLANNED, IN_PROGRESS, DONE, PACKAGED, DELIVERED, VERIFIED')
    completed_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    verified_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    verification_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    delivered_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    completed_by_user: Mapped['User'] = relationship('User', foreign_keys=[completed_by], back_populates='Launch_completed_by')
    delivery_method: Mapped['DeliveryMethod'] = relationship('DeliveryMethod', back_populates='Launch')
    receiver: Mapped['ManufacturingReceiver'] = relationship('ManufacturingReceiver', back_populates='Launch')
    verification_document: Mapped['Document'] = relationship('Document', back_populates='Launch')
    verified_by_user: Mapped['User'] = relationship('User', foreign_keys=[verified_by], back_populates='Launch_verified_by')
    CuttingConsumption: Mapped[list['CuttingConsumption']] = relationship('CuttingConsumption', back_populates='launch')
    LaunchFGPN: Mapped[list['LaunchFGPN']] = relationship('LaunchFGPN', back_populates='launch')
    LaunchPO: Mapped[list['LaunchPO']] = relationship('LaunchPO', back_populates='launch')
    LaunchVerification: Mapped[list['LaunchVerification']] = relationship('LaunchVerification', back_populates='launch')


class PurchaseOrderLine(Base):
    __tablename__ = 'PurchaseOrderLine'
    __table_args__ = (
        ForeignKeyConstraint(['delivery_method_id'], ['DeliveryMethod.delivery_method_id'], deferrable=True, name='PurchaseOrderLine_delivery_method_id_fkey'),
        ForeignKeyConstraint(['fgpn_id'], ['FGPN.fgpn_id'], deferrable=True, name='PurchaseOrderLine_fgpn_id_fkey'),
        ForeignKeyConstraint(['po_version_id'], ['PurchaseOrderVersion.po_version_id'], deferrable=True, name='PurchaseOrderLine_po_version_id_fkey'),
        PrimaryKeyConstraint('po_line_id', name='PurchaseOrderLine_pkey'),
        Index('PurchaseOrderLine_po_version_id_fgpn_id_idx', 'po_version_id', 'fgpn_id', unique=True),
        Index('PurchaseOrderLine_po_version_id_line_number_idx', 'po_version_id', 'line_number', unique=True)
    )

    po_line_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    po_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fgpn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ordered_quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    delivery_method_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    item_number: Mapped[Optional[str]] = mapped_column(String(50))
    development_level: Mapped[Optional[str]] = mapped_column(String(50))
    color_code: Mapped[Optional[str]] = mapped_column(String(4))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    trim_code: Mapped[Optional[str]] = mapped_column(String(50))
    delivery_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    pickup_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    delivery_method: Mapped['DeliveryMethod'] = relationship('DeliveryMethod', back_populates='PurchaseOrderLine')
    fgpn: Mapped['FGPN'] = relationship('FGPN', back_populates='PurchaseOrderLine')
    po_version: Mapped['PurchaseOrderVersion'] = relationship('PurchaseOrderVersion', back_populates='PurchaseOrderLine')
    LaunchFGPN: Mapped[list['LaunchFGPN']] = relationship('LaunchFGPN', back_populates='po_line')


class StockAllocation(Base):
    __tablename__ = 'StockAllocation'
    __table_args__ = (
        ForeignKeyConstraint(['simulation_id'], ['Simulation.simulation_id'], deferrable=True, name='StockAllocation_simulation_id_fkey'),
        PrimaryKeyConstraint('allocation_id', name='StockAllocation_pkey')
    )

    allocation_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    source_location: Mapped[str] = mapped_column(String(20), nullable=False, comment='WAREHOUSE, PRODUCTION')
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'Reserved'::character varying"), comment='Reserved, Released, Delivered')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    simulation: Mapped['Simulation'] = relationship('Simulation', back_populates='StockAllocation')


class StockIssueHandover(Base):
    __tablename__ = 'StockIssueHandover'
    __table_args__ = (
        ForeignKeyConstraint(['signed_document_id'], ['Document.document_id'], deferrable=True, name='StockIssueHandover_signed_document_id_fkey'),
        ForeignKeyConstraint(['simulation_id'], ['Simulation.simulation_id'], deferrable=True, name='StockIssueHandover_simulation_id_fkey'),
        PrimaryKeyConstraint('delivery_inst_id', name='StockIssueHandover_pkey'),
        UniqueConstraint('delivery_code', name='StockIssueHandover_delivery_code_key')
    )

    delivery_inst_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_code: Mapped[str] = mapped_column(String(10), nullable=False)
    code_expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    signed_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'Draft'::character varying"), comment='Draft, Code_Generated, Document_Generated, Signed_Uploaded, Validated, Expired')
    receiver_name: Mapped[Optional[str]] = mapped_column(String(100))
    uploaded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    uploader_username: Mapped[Optional[str]] = mapped_column(String(50))
    validation_username: Mapped[Optional[str]] = mapped_column(String(50))
    validation_timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    signed_document: Mapped['Document'] = relationship('Document', back_populates='StockIssueHandover')
    simulation: Mapped['Simulation'] = relationship('Simulation', back_populates='StockIssueHandover')


class BOMLine(Base):
    __tablename__ = 'BOMLine'
    __table_args__ = (
        ForeignKeyConstraint(['bom_id'], ['BOM.bom_id'], deferrable=True, name='BOMLine_bom_id_fkey'),
        ForeignKeyConstraint(['material_part_number'], ['Material.material_part_number'], deferrable=True, name='BOMLine_material_part_number_fkey'),
        PrimaryKeyConstraint('bom_line_id', name='BOMLine_pkey'),
        Index('BOMLine_bom_id_line_number_idx', 'bom_id', 'line_number', unique=True)
    )

    bom_line_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(Integer, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_part_number: Mapped[str] = mapped_column(String(10), nullable=False)
    coefficient: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    part_type: Mapped[Optional[str]] = mapped_column(String(5))
    cover_revision: Mapped[Optional[str]] = mapped_column(String(50))
    cover_pn: Mapped[Optional[str]] = mapped_column(String(50))
    quantity_tpdm: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    cover_description: Mapped[Optional[str]] = mapped_column(String(200))
    total_quantity: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    total_sqm: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 10))

    bom: Mapped['BOM'] = relationship('BOM', back_populates='BOMLine')
    Material_: Mapped['Material'] = relationship('Material', back_populates='BOMLine')
    
    @property
    def source_row_number(self) -> int:
        return self.line_number

    @property
    def quantity(self) -> decimal.Decimal:
        return self.usage_quantity

    @property
    def cover_revision(self) -> Optional[str]:
        return self.part_revision

    @property
    def total_quantity(self) -> Optional[decimal.Decimal]:
        return self.base_quantity

    @property
    def coefficient(self) -> decimal.Decimal:
        return decimal.Decimal("1.0000")  # Default multiplier/coefficient

    @property
    def material_description(self) -> Optional[str]:
        return self.Material_.description if self.Material_ else None


class CuttingConsumption(Base):
    __tablename__ = 'CuttingConsumption'
    __table_args__ = (
        ForeignKeyConstraint(['cutman_document_id'], ['Document.document_id'], deferrable=True, name='CuttingConsumption_cutman_document_id_fkey'),
        ForeignKeyConstraint(['launch_id'], ['Launch.launch_id'], deferrable=True, name='CuttingConsumption_launch_id_fkey'),
        ForeignKeyConstraint(['material_part_number'], ['Material.material_part_number'], deferrable=True, name='CuttingConsumption_material_part_number_fkey'),
        PrimaryKeyConstraint('consumption_id', name='CuttingConsumption_pkey')
    )

    consumption_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    launch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    material_part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity_consumed: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cutman_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    nesting_name: Mapped[Optional[str]] = mapped_column(String(100))

    cutman_document: Mapped['Document'] = relationship('Document', back_populates='CuttingConsumption')
    launch: Mapped['Launch'] = relationship('Launch', back_populates='CuttingConsumption')
    Material_: Mapped['Material'] = relationship('Material', back_populates='CuttingConsumption')


class LaunchFGPN(Base):
    __tablename__ = 'LaunchFGPN'
    __table_args__ = (
        ForeignKeyConstraint(['fgpn_id'], ['FGPN.fgpn_id'], deferrable=True, name='LaunchFGPN_fgpn_id_fkey'),
        ForeignKeyConstraint(['launch_id'], ['Launch.launch_id'], deferrable=True, name='LaunchFGPN_launch_id_fkey'),
        ForeignKeyConstraint(['po_line_id'], ['PurchaseOrderLine.po_line_id'], deferrable=True, name='LaunchFGPN_po_line_id_fkey'),
        PrimaryKeyConstraint('launch_fgpn_id', name='LaunchFGPN_pkey'),
        Index('LaunchFGPN_launch_id_fgpn_id_po_line_id_idx', 'launch_id', 'fgpn_id', 'po_line_id', unique=True)
    )

    launch_fgpn_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    launch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fgpn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    po_line_id: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_quantity: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    fgpn: Mapped['FGPN'] = relationship('FGPN', back_populates='LaunchFGPN')
    launch: Mapped['Launch'] = relationship('Launch', back_populates='LaunchFGPN')
    po_line: Mapped['PurchaseOrderLine'] = relationship('PurchaseOrderLine', back_populates='LaunchFGPN')


class LaunchPO(Base):
    __tablename__ = 'LaunchPO'
    __table_args__ = (
        ForeignKeyConstraint(['launch_id'], ['Launch.launch_id'], deferrable=True, name='LaunchPO_launch_id_fkey'),
        ForeignKeyConstraint(['po_id'], ['PurchaseOrder.po_id'], deferrable=True, name='LaunchPO_po_id_fkey'),
        PrimaryKeyConstraint('launch_po_id', name='LaunchPO_pkey'),
        Index('LaunchPO_launch_id_po_id_idx', 'launch_id', 'po_id', unique=True)
    )

    launch_po_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    launch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    po_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    launch: Mapped['Launch'] = relationship('Launch', back_populates='LaunchPO')
    po: Mapped['PurchaseOrder'] = relationship('PurchaseOrder', back_populates='LaunchPO')


class LaunchVerification(Base):
    __tablename__ = 'LaunchVerification'
    __table_args__ = (
        ForeignKeyConstraint(['engineer_document_id'], ['Document.document_id'], deferrable=True, name='LaunchVerification_engineer_document_id_fkey'),
        ForeignKeyConstraint(['launch_id'], ['Launch.launch_id'], deferrable=True, name='LaunchVerification_launch_id_fkey'),
        ForeignKeyConstraint(['summary_document_id'], ['Document.document_id'], deferrable=True, name='LaunchVerification_summary_document_id_fkey'),
        ForeignKeyConstraint(['verified_by'], ['users.id'], deferrable=True, name='LaunchVerification_verified_by_fkey'),
        PrimaryKeyConstraint('verification_id', name='LaunchVerification_pkey')
    )

    verification_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True, autoincrement=True)
    launch_id: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    engineer_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    verified_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, comment='PENDING, VERIFIED, REJECTED')
    remarks: Mapped[Optional[str]] = mapped_column(Text)

    engineer_document: Mapped['Document'] = relationship('Document', foreign_keys=[engineer_document_id], back_populates='LaunchVerification_engineer_document')
    launch: Mapped['Launch'] = relationship('Launch', back_populates='LaunchVerification')
    summary_document: Mapped['Document'] = relationship('Document', foreign_keys=[summary_document_id], back_populates='LaunchVerification_summary_document')
    user: Mapped['User'] = relationship('User', back_populates='LaunchVerification')
