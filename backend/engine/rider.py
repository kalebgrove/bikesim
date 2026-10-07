class Rider:
    def __init__(self, rider_mass, bike_mass, ftp, f_max, cda, crr, inertia, wheel_radius, metabolic_efficiency):
        self.name = "Test Rider"
        self.mass = rider_mass + bike_mass
        self.ftp = ftp
        self.f_max = f_max
        self.cda = cda
        self.crr = crr
        self.inertia = inertia
        self.wheel_radius = wheel_radius
        self.metabolic_efficiency = metabolic_efficiency

    @property
    def effective_mass(self) -> float:
        # Accelerating the bike also spins up the wheels: m_eff = m + I / r^2 (kg),
        # with inertia = I of BOTH wheels combined (kg*m^2), wheel_radius r (m).
        # Use m_eff for F = m_eff * a only; gravity and rolling still use self.mass.
        return self.mass + self.inertia / self.wheel_radius ** 2

    # def test_rider(self):
    #     self.name = input("Enter rider name: ")
    #     self.mass = float(input("Enter rider mass (kg): ")) + float(input("Enter bike mass (kg): "))
    #     self.ftp = float(input("Enter FTP (W): "))
    #     self.f_max = float(input("Enter maximum force (N): "))
    #     self.cda = float(input("Enter drag area (m²): "))
    #     self.crr = float(input("Enter rolling resistance coefficient: "))
    #     self.inertia = float(input("Enter inertia (kg·m²): "))
    #     self.wheel_radius = float(input("Enter wheel radius (m): "))
    #     self.metabolic_efficiency = float(input("Enter metabolic efficiency: "))