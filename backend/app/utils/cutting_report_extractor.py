"""Read the tabular CutMan XLSX export without inferring remaining stock or launch IDs."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

from app.exceptions.base import ValidationException
from app.utils.bom_workbook_extractor import _find_sheet_path, _read_shared_strings, _read_sheet_rows


@dataclass(frozen=True)
class CuttingReportRow:
    sheet: str
    row_number: int
    material_part_number: str
    description: str
    started_at: datetime
    spreading_usage: Decimal
    raw_fields: dict[str, str]

    @property
    def fingerprint(self) -> str:
        # No native event ID is supplied. Exact repeated source events require
        # reconciliation rather than a second automatic consumption posting.
        identity_fields = ("Original nesting name", "Produced nesting name", "Batch number", "Cutter", "Table")
        payload = {field: self.raw_fields.get(field, "") for field in identity_fields}
        payload["Material"] = self.material_part_number
        payload["Start date"] = self.started_at.date().isoformat()
        payload["Start time"] = self.started_at.time().isoformat()
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def as_dict(self) -> dict:
        return {"sheet": self.sheet, "row_number": self.row_number,
                "material_part_number": self.material_part_number, "description": self.description,
                "started_at": self.started_at.isoformat(), "spreading_usage": str(self.spreading_usage),
                "fingerprint": self.fingerprint, "raw_fields": self.raw_fields}


def extract_cutting_report(content: bytes, filename: str) -> list[CuttingReportRow]:
    if not filename.lower().endswith(".xlsx"):
        raise ValidationException("Cutting reports must be .xlsx workbooks.")
    if len(content) > 20 * 1024 * 1024:
        raise ValidationException("Cutting report exceeds the 20 MB limit.")
    try:
        with ZipFile(BytesIO(content)) as workbook:
            if sum(info.file_size for info in workbook.infolist()) > 100 * 1024 * 1024:
                raise ValidationException("Expanded cutting report exceeds the 100 MB limit.")
            shared = _read_shared_strings(workbook)
            root = ET.fromstring(workbook.read("xl/workbook.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            results = []
            required = {"Start date", "Start time", "Material", "Spreading Usage"}
            for sheet in root.findall("m:sheets/m:sheet", ns):
                name = sheet.attrib["name"]
                rows = _read_sheet_rows(workbook, _find_sheet_path(workbook, name), shared)
                header = None
                for number, cells in rows.items():
                    if not any(str(value).strip() for value in cells.values()):
                        continue
                    if required <= {str(value).strip() for value in cells.values()}:
                        header = {column: str(value).strip() for column, value in cells.items() if str(value).strip()}
                        continue
                    if header is None:
                        continue
                    fields = {label: str(cells.get(column, "")).strip() for column, label in header.items()}
                    material = fields.get("Material", "")
                    if not material or len(material) > 50:
                        raise ValidationException(f"{name} row {number}: a material number of at most 50 characters is required.")
                    try:
                        started = datetime.strptime(f"{fields['Start date']} {fields['Start time']}", "%d/%m/%Y %H:%M:%S")
                        usage = Decimal(fields["Spreading Usage"].replace(",", "."))
                        if not usage.is_finite() or usage <= 0:
                            raise ValueError("nonpositive usage")
                    except (ValueError, InvalidOperation) as exc:
                        raise ValidationException(f"{name} row {number}: invalid start date/time or positive Spreading Usage.") from exc
                    results.append(CuttingReportRow(name, number, material, fields.get("Description", ""), started, usage, fields))
            if not results:
                raise ValidationException("No cutting rows found. Expected Start date, Start time, Material and Spreading Usage headers.")
            return results
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValidationException("Invalid or unsupported XLSX cutting report.") from exc
