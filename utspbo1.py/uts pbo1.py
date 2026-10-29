"""
UTS PEMROGRAMAN BERORIENTASI OBJEK
Konsep : Rule (validasi), Inheritance, Polymorphism, Override
Data   : employee.json  &  sensor_logs.json

Cara jalanin:  python main.py
(File JSON otomatis dibuat di folder yang sama kalau belum ada)

STRUKTUR "STACK" KODE (dari bawah ke atas):
  Layer 0 - Exception        : ValidationError
  Layer 1 - Base class       : BaseRecord (abstract)
  Layer 2 - Model Employee   : Employee -> Contract / Permanent -> Manager
  Layer 3 - Model Sensor     : Sensor   -> Normal / Warning / Danger
  Layer 4 - Factory          : EmployeeFactory, SensorFactory
  Layer 5 - Repository       : JsonRepository (baca file JSON)
  Layer 6 - Service          : PayrollService, SensorMonitor (laporan)
  Layer 7 - Main program
"""

import json
import os
from abc import ABC, abstractmethod
from collections import Counter, defaultdict

EMPLOYEE_FILE = "employee.json"
SENSOR_FILE = "sensor_logs.json"


def rupiah(nilai):
    """Format angka jadi Rp 1.234.567"""
    return "Rp {:,.0f}".format(nilai).replace(",", ".")


# =====================================================================
# LAYER 0 - EXCEPTION
# =====================================================================
class ValidationError(Exception):
    """Dilempar kalau data melanggar RULE."""


# =====================================================================
# LAYER 1 - BASE CLASS (parent paling atas, abstract)
# =====================================================================
class BaseRecord(ABC):
    """Parent untuk semua data (Employee & Sensor)."""

    def __init__(self, record_id):
        self._record_id = record_id  # protected

    @property
    def record_id(self):
        return self._record_id

    @abstractmethod
    def validate(self):
        """Cek RULE data. Wajib di-override anak class."""

    @abstractmethod
    def summary(self):
        """Ringkasan 1 baris. Wajib di-override anak class."""

    def __str__(self):
        return self.summary()


# =====================================================================
# LAYER 2 - MODEL EMPLOYEE (Inheritance bertingkat)
#   BaseRecord -> Employee -> ContractEmployee
#                          -> PermanentEmployee -> ManagerEmployee
# =====================================================================
class Employee(BaseRecord):
    # RULE: persentase bonus berdasarkan bonus_code (dari gaji pokok)
    BONUS_RATES = {"PERF2026": 0.15, "SENIOR10": 0.10, "LEAD2026": 0.20}
    TAX_RATE = 0.0  # akan di-override tiap jenis karyawan

    def __init__(self, emp_id, name, base_salary, is_permanent, bonus_code=None):
        super().__init__(emp_id)
        self.name = name
        self.base_salary = base_salary
        self.is_permanent = is_permanent
        self.bonus_code = bonus_code
        self.validate()

    # ---- RULE validasi ----
    def validate(self):
        if not str(self.record_id).startswith("EMP-"):
            raise ValidationError("emp_id harus diawali 'EMP-': {}".format(self.record_id))
        if not self.name or not str(self.name).strip():
            raise ValidationError("{}: nama tidak boleh kosong".format(self.record_id))
        if not isinstance(self.base_salary, (int, float)) or self.base_salary <= 0:
            raise ValidationError("{}: base_salary harus > 0".format(self.record_id))
        if self.bonus_code is not None and self.bonus_code not in self.BONUS_RATES:
            raise ValidationError(
                "{}: bonus_code tidak dikenal '{}'".format(self.record_id, self.bonus_code)
            )

    # ---- method abstract (wajib di-override) ----
    @abstractmethod
    def get_role(self):
        """Nama jabatan/status karyawan."""

    @abstractmethod
    def calculate_bonus(self):
        """Hitung bonus."""

    # ---- method default (boleh di-override) ----
    def calculate_allowance(self):
        return 0.0

    def gross_salary(self):
        return self.base_salary + self.calculate_allowance() + self.calculate_bonus()

    def calculate_tax(self):
        return self.gross_salary() * self.TAX_RATE

    def net_salary(self):
        return self.gross_salary() - self.calculate_tax()

    def summary(self):
        return "[{:<8}] {} | {:<17} | Bonus: {:<10} | Gaji bersih: {}".format(
            self.get_role(),
            self.record_id,
            self.name,
            str(self.bonus_code),
            rupiah(self.net_salary()),
        )


class ContractEmployee(Employee):
    """Karyawan kontrak: tanpa tunjangan, tanpa bonus, pajak 2.5%."""

    TAX_RATE = 0.025  # OVERRIDE

    def get_role(self):  # OVERRIDE
        return "Kontrak"

    def calculate_bonus(self):  # OVERRIDE
        # RULE: karyawan kontrak tidak berhak bonus, walau punya bonus_code
        return 0.0


class PermanentEmployee(Employee):
    """Karyawan tetap: tunjangan tetap 10% + bonus sesuai kode, pajak 5%."""

    TAX_RATE = 0.05  # OVERRIDE
    ALLOWANCE_RATE = 0.10

    def get_role(self):  # OVERRIDE
        return "Tetap"

    def calculate_allowance(self):  # OVERRIDE
        return self.base_salary * self.ALLOWANCE_RATE

    def calculate_bonus(self):  # OVERRIDE
        if self.bonus_code is None:
            return 0.0
        return self.base_salary * self.BONUS_RATES[self.bonus_code]


class ManagerEmployee(PermanentEmployee):
    """Manager (kode LEAD2026): tunjangan jabatan tambahan, pajak 7.5%."""

    TAX_RATE = 0.075  # OVERRIDE
    LEADERSHIP_ALLOWANCE = 2_000_000

    def get_role(self):  # OVERRIDE
        return "Manager"

    def calculate_allowance(self):  # OVERRIDE + pakai super()
        return super().calculate_allowance() + self.LEADERSHIP_ALLOWANCE


# =====================================================================
# LAYER 3 - MODEL SENSOR
#   BaseRecord -> Sensor -> NormalSensor / WarningSensor / DangerSensor
# =====================================================================
class Sensor(BaseRecord):
    # RULE ambang suhu
    DANGER_MIN = 85.0   # suhu >= 85  -> DANGER
    WARNING_MIN = 60.0  # 60 <= suhu < 85 -> WARNING, selain itu NORMAL

    STATUS = None    # di-override anak class
    PRIORITY = 0     # di-override anak class

    def __init__(self, sensor_id, location, temperature, status, operator_id=None):
        super().__init__(sensor_id)
        self.location = location
        self.temperature = temperature
        self.status = status
        self.operator_id = operator_id
        self.validate()

    @staticmethod
    def status_from_temperature(temp):
        if temp >= Sensor.DANGER_MIN:
            return "DANGER"
        if temp >= Sensor.WARNING_MIN:
            return "WARNING"
        return "NORMAL"

    # ---- RULE validasi ----
    def validate(self):
        if not str(self.record_id).startswith("SNS-"):
            raise ValidationError("sensor_id harus diawali 'SNS-': {}".format(self.record_id))
        if not self.location:
            raise ValidationError("{}: location kosong".format(self.record_id))
        if not isinstance(self.temperature, (int, float)) or not (-50 <= self.temperature <= 200):
            raise ValidationError("{}: suhu tidak valid".format(self.record_id))
        if self.status != self.STATUS:
            raise ValidationError("{}: status '{}' tidak cocok".format(self.record_id, self.status))
        expected = self.status_from_temperature(self.temperature)
        if expected != self.status:
            raise ValidationError(
                "{}: suhu {} seharusnya {}, bukan {}".format(
                    self.record_id, self.temperature, expected, self.status
                )
            )

    def has_operator(self):
        return self.operator_id is not None

    def operator_note(self):
        return "" if self.has_operator() else " | !! OPERATOR BELUM DITUGASKAN !!"

    @abstractmethod
    def get_action(self):
        """Tindakan yang harus dilakukan. Wajib di-override."""

    def summary(self):
        return "[{:<7}] {} | {:<13} | {:>5.1f} C | Operator: {:<4} | {}".format(
            self.status,
            self.record_id,
            self.location,
            self.temperature,
            str(self.operator_id),
            self.get_action(),
        )


class NormalSensor(Sensor):
    STATUS = "NORMAL"  # OVERRIDE
    PRIORITY = 0       # OVERRIDE

    def get_action(self):  # OVERRIDE
        return "Aman, pantau rutin"


class WarningSensor(Sensor):
    STATUS = "WARNING"  # OVERRIDE
    PRIORITY = 1        # OVERRIDE

    def get_action(self):  # OVERRIDE
        return "Waspada, cek dalam 1 jam" + self.operator_note()


class DangerSensor(Sensor):
    STATUS = "DANGER"  # OVERRIDE
    PRIORITY = 2       # OVERRIDE

    def get_action(self):  # OVERRIDE
        if self.has_operator():
            return "BAHAYA, operator {} tangani segera".format(self.operator_id)
        return "BAHAYA, eskalasi ke supervisor" + self.operator_note()


# =====================================================================
# LAYER 4 - FACTORY (memilih class yang tepat berdasarkan RULE)
# =====================================================================
class EmployeeFactory:
    @staticmethod
    def create(data):
        args = (data["emp_id"], data["name"], data["base_salary"])
        is_permanent = data["is_permanent"]
        bonus_code = data.get("bonus_code")

        if not is_permanent:
            return ContractEmployee(*args, is_permanent, bonus_code)
        if bonus_code == "LEAD2026":
            return ManagerEmployee(*args, is_permanent, bonus_code)
        return PermanentEmployee(*args, is_permanent, bonus_code)


class SensorFactory:
    MAPPING = {"NORMAL": NormalSensor, "WARNING": WarningSensor, "DANGER": DangerSensor}

    @staticmethod
    def create(data):
        cls = SensorFactory.MAPPING.get(data["status"])
        if cls is None:
            raise ValidationError("{}: status '{}' tidak dikenal".format(data["sensor_id"], data["status"]))
        return cls(
            data["sensor_id"],
            data["location"],
            data["temperature"],
            data["status"],
            data.get("operator_id"),
        )


# =====================================================================
# LAYER 5 - REPOSITORY (baca file JSON)
# =====================================================================
class JsonRepository:
    def __init__(self, filename, root_key):
        self.filename = filename
        self.root_key = root_key

    def load_raw(self):
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f).get(self.root_key, [])
        except FileNotFoundError:
            print("File tidak ditemukan:", self.filename)
        except json.JSONDecodeError as e:
            print("Format JSON rusak di {}: {}".format(self.filename, e))
        return []

    def load_objects(self, factory):
        """Return (daftar objek valid, daftar error)."""
        objects, errors = [], []
        for item in self.load_raw():
            try:
                objects.append(factory.create(item))
            except (ValidationError, KeyError, TypeError) as e:
                errors.append(str(e))
        return objects, errors


# =====================================================================
# LAYER 6 - SERVICE (laporan)
# =====================================================================
class PayrollService:
    def __init__(self, employees):
        self.employees = employees

    def total_net(self):
        return sum(e.net_salary() for e in self.employees)

    def group_by_role(self):
        grouped = defaultdict(list)
        for e in self.employees:
            grouped[e.get_role()].append(e)  # POLYMORPHISM: get_role beda tiap class
        return grouped

    def top_earners(self, n=5):
        return sorted(self.employees, key=lambda e: e.net_salary(), reverse=True)[:n]

    def print_report(self):
        print("=" * 100)
        print("LAPORAN PENGGAJIAN KARYAWAN")
        print("=" * 100)
        for e in self.employees:
            print(e)  # POLYMORPHISM: summary() & net_salary() beda perhitungan tiap class
        print("-" * 100)
        for role, items in self.group_by_role().items():
            total = sum(x.net_salary() for x in items)
            print("{:<8}: {:>2} orang | Total gaji bersih {}".format(role, len(items), rupiah(total)))
        print("-" * 100)
        print("TOTAL PENGELUARAN GAJI BERSIH:", rupiah(self.total_net()))
        print("\nTop 5 gaji bersih tertinggi:")
        for i, e in enumerate(self.top_earners(), 1):
            print("  {}. {:<17} ({}) {}".format(i, e.name, e.get_role(), rupiah(e.net_salary())))


class SensorMonitor:
    def __init__(self, sensors):
        self.sensors = sensors

    def count_by_status(self):
        return Counter(s.status for s in self.sensors)

    def avg_temp_by_location(self):
        temps = defaultdict(list)
        for s in self.sensors:
            temps[s.location].append(s.temperature)
        return {loc: sum(v) / len(v) for loc, v in temps.items()}

    def unattended_alerts(self):
        """WARNING/DANGER yang tidak punya operator."""
        return [s for s in self.sensors if s.PRIORITY > 0 and not s.has_operator()]

    def operator_workload(self):
        return Counter(s.operator_id for s in self.sensors if s.has_operator())

    def print_report(self):
        print("=" * 100)
        print("LAPORAN MONITORING SENSOR")
        print("=" * 100)
        # diurutkan dari prioritas tertinggi (DANGER dulu), lalu suhu tertinggi
        for s in sorted(self.sensors, key=lambda x: (-x.PRIORITY, -x.temperature)):
            print(s)  # POLYMORPHISM: get_action() beda tiap class
        print("-" * 100)
        print("Jumlah per status :", dict(self.count_by_status()))
        print("\nRata-rata suhu per lokasi:")
        for loc, avg in sorted(self.avg_temp_by_location().items(), key=lambda x: -x[1]):
            print("  {:<14}: {:.1f} C".format(loc, avg))
        print("\nBeban kerja operator (jumlah sensor):")
        for op, n in sorted(self.operator_workload().items()):
            print("  Operator {}: {} sensor".format(op, n))
        print("\nALERT TANPA OPERATOR ({} sensor):".format(len(self.unattended_alerts())))
        for s in self.unattended_alerts():
            print("  -", s.record_id, s.location, s.status, s.temperature, "C")
        hottest = max(self.sensors, key=lambda s: s.temperature)
        print("\nSensor terpanas: {} di {} ({} C)".format(hottest.record_id, hottest.location, hottest.temperature))


def tampilkan_semua(records):
    """POLYMORPHISM murni: Employee & Sensor sama-sama BaseRecord,
    cukup panggil summary() tanpa peduli tipe aslinya."""
    for r in records:
        print(" ", r.summary())


# =====================================================================
# DATA BAWAAN (supaya script langsung jalan tanpa file eksternal)
# =====================================================================
EMPLOYEE_ROWS = [
    ("EMP-001", "Budi Pratama", 8500000.0, True, "PERF2026"),
    ("EMP-002", "Siti Rahma", 6000000.0, False, None),
    ("EMP-003", "Andi Wijaya", 12500000.0, True, None),
    ("EMP-004", "Dewi Lestari", 7200000.0, True, "PERF2026"),
    ("EMP-005", "Eko Prasetyo", 5500000.0, False, None),
    ("EMP-006", "Fajar Nugraha", 9800000.0, True, "SENIOR10"),
    ("EMP-007", "Gita Gutawa", 6800000.0, False, None),
    ("EMP-008", "Hendra Kurniawan", 11000000.0, True, "PERF2026"),
    ("EMP-009", "Indah Permata", 8000000.0, True, None),
    ("EMP-010", "Joko Widodo", 5000000.0, False, None),
    ("EMP-011", "Kiki Amalia", 7700000.0, True, "PERF2026"),
    ("EMP-012", "Lukman Hakim", 13500000.0, True, "LEAD2026"),
    ("EMP-013", "Maya Putri", 6200000.0, False, None),
    ("EMP-014", "Nurdin Hasan", 8900000.0, True, None),
    ("EMP-015", "Oki Setiana", 9500000.0, True, "PERF2026"),
    ("EMP-016", "Panji Petualang", 5800000.0, False, None),
    ("EMP-017", "Qory Sandioriva", 10500000.0, True, "SENIOR10"),
    ("EMP-018", "Rian D'Masiv", 7000000.0, True, None),
    ("EMP-019", "Siska Kohl", 14000000.0, True, "LEAD2026"),
    ("EMP-020", "Tora Sudiro", 6400000.0, False, None),
    ("EMP-021", "Uus Kartajaya", 8300000.0, True, "PERF2026"),
    ("EMP-022", "Vina Panduwinata", 9100000.0, True, None),
    ("EMP-023", "Wendra Pratama", 5300000.0, False, None),
    ("EMP-024", "Xavier Marks", 11800000.0, True, "SENIOR10"),
    ("EMP-025", "Yuni Shara", 7600000.0, True, None),
    ("EMP-026", "Zainal Abidin", 6500000.0, False, None),
    ("EMP-027", "Ahmad Dhani", 15000000.0, True, "LEAD2026"),
    ("EMP-028", "Bella Saphira", 8200000.0, True, "PERF2026"),
    ("EMP-029", "Cinta Laura", 10000000.0, True, None),
    ("EMP-030", "Deddy Corbuzier", 6100000.0, False, None),
]

SENSOR_ROWS = [
    ("SNS-A01", "Boiler Room", 88.5, "DANGER", 101),
    ("SNS-A02", "Assembly Line", 42.0, "NORMAL", 102),
    ("SNS-A03", "Server Room", 95.2, "DANGER", None),
    ("SNS-A04", "Chemical Lab", 73.1, "WARNING", 104),
    ("SNS-A05", "Boiler Room", 91.0, "DANGER", 101),
    ("SNS-A06", "Warehouse", 31.5, "NORMAL", None),
    ("SNS-A07", "Turbine House", 87.3, "DANGER", 107),
    ("SNS-A08", "Assembly Line", 45.8, "NORMAL", 102),
    ("SNS-A09", "Server Room", 89.9, "DANGER", 109),
    ("SNS-A10", "Data Center", 24.0, "NORMAL", None),
    ("SNS-A11", "Boiler Room", 96.4, "DANGER", 101),
    ("SNS-A12", "Chemical Lab", 68.0, "WARNING", 104),
    ("SNS-A13", "Turbine House", 92.1, "DANGER", None),
    ("SNS-A14", "Warehouse", 29.8, "NORMAL", 114),
    ("SNS-A15", "Server Room", 86.0, "DANGER", 109),
    ("SNS-A16", "Assembly Line", 41.2, "NORMAL", 102),
    ("SNS-A17", "Boiler Room", 99.5, "DANGER", 101),
    ("SNS-A18", "Data Center", 22.5, "NORMAL", None),
    ("SNS-A19", "Turbine House", 88.0, "DANGER", 107),
    ("SNS-A20", "Chemical Lab", 75.4, "WARNING", None),
    ("SNS-A21", "Boiler Room", 90.2, "DANGER", 101),
    ("SNS-A22", "Assembly Line", 39.9, "NORMAL", 122),
    ("SNS-A23", "Server Room", 93.7, "DANGER", 109),
    ("SNS-A24", "Warehouse", 30.0, "NORMAL", None),
    ("SNS-A25", "Turbine House", 87.8, "DANGER", 107),
    ("SNS-A26", "Data Center", 25.1, "NORMAL", 126),
    ("SNS-A27", "Boiler Room", 97.0, "DANGER", None),
    ("SNS-A28", "Chemical Lab", 71.3, "WARNING", 104),
    ("SNS-A29", "Server Room", 85.5, "DANGER", 109),
    ("SNS-A30", "Assembly Line", 43.5, "NORMAL", None),
]


def ensure_json_files():
    """Bikin employee.json & sensor_logs.json kalau belum ada."""
    if not os.path.exists(EMPLOYEE_FILE):
        data = {"employees": [
            {"emp_id": a, "name": b, "base_salary": c, "is_permanent": d, "bonus_code": e}
            for a, b, c, d, e in EMPLOYEE_ROWS
        ]}
        with open(EMPLOYEE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[info] {} dibuat".format(EMPLOYEE_FILE))

    if not os.path.exists(SENSOR_FILE):
        data = {"readings": [
            {"sensor_id": a, "location": b, "temperature": c, "status": d, "operator_id": e}
            for a, b, c, d, e in SENSOR_ROWS
        ]}
        with open(SENSOR_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[info] {} dibuat".format(SENSOR_FILE))


# =====================================================================
# LAYER 7 - MAIN
# =====================================================================
def main():
    ensure_json_files()

    employees, emp_errors = JsonRepository(EMPLOYEE_FILE, "employees").load_objects(EmployeeFactory)
    sensors, sns_errors = JsonRepository(SENSOR_FILE, "readings").load_objects(SensorFactory)

    PayrollService(employees).print_report()
    print()
    SensorMonitor(sensors).print_report()

    print("\n" + "=" * 100)
    print("DEMO POLYMORPHISM: Employee & Sensor diproses lewat satu fungsi yang sama")
    print("=" * 100)
    tampilkan_semua([employees[0], employees[11], employees[1], sensors[0], sensors[1], sensors[3]])

    print("\n" + "=" * 100)
    print("DATA DITOLAK (melanggar rule): {}".format(len(emp_errors) + len(sns_errors)))
    for err in emp_errors + sns_errors:
        print("  -", err)

    # Demo rule: data yang salah akan ditolak
    print("\nDemo validasi (data sengaja salah):")
    contoh_salah = [
        {"emp_id": "EMP-999", "name": "Tes", "base_salary": -100, "is_permanent": True, "bonus_code": None},
        {"emp_id": "EMP-998", "name": "Tes2", "base_salary": 5000000, "is_permanent": True, "bonus_code": "XXX"},
    ]
    for d in contoh_salah:
        try:
            EmployeeFactory.create(d)
        except ValidationError as e:
            print("  DITOLAK ->", e)


if __name__ == "__main__":
    main()