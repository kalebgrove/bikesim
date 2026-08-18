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

    def test_rider(self):
        self.name = input("Enter rider name: ")
        self.mass = float(input("Enter rider mass (kg): ")) + float(input("Enter bike mass (kg): "))
        self.ftp = float(input("Enter FTP (W): "))
        self.f_max = float(input("Enter maximum force (N): "))
        self.cda = float(input("Enter drag area (m²): "))
        self.crr = float(input("Enter rolling resistance coefficient: "))
        self.inertia = float(input("Enter inertia (kg·m²): "))
        self.wheel_radius = float(input("Enter wheel radius (m): "))
        self.metabolic_efficiency = float(input("Enter metabolic efficiency: "))