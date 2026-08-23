#File that contains the route class and its methods.

import xml.etree.ElementTree as ET
import math
import matplotlib.pyplot as plt
from bisect import bisect_right

class Route:
    @classmethod

    def get_route_from_gpx(cls, filepath):
        #Read a gpx and extract route information (lat and lon for example)
        tree = ET.parse(filepath)
        return cls._from_root(tree.getroot())

    @classmethod
    def get_route_from_bytes(cls, data: bytes):
        #Parse GPX content already loaded (e.g. downloaded from Supabase Storage)
        return cls._from_root(ET.fromstring(data))

    @classmethod
    def _from_root(cls, root):
        #Find all points from the route and elevation data
        points = []
        ns = {'gpx': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

        for trkpt in root.iter(f"{{{ns['gpx']}}}trkpt" if ns else "trkpt"):
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
            ele_elem = trkpt.find(f"{{{ns['gpx']}}}ele" if ns else "ele")
            ele = float(ele_elem.text) if ele_elem is not None else 0.0
            points.append((lat, lon, ele))

        return cls(points)

    @staticmethod
    def haversine_distance(position1, position2) -> float:
        #Calculates the distance between two positions

        lat1, lon1 = math.radians(position1[0]), math.radians(position1[1])
        lat2, lon2 = math.radians(position2[0]), math.radians(position2[1])

        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1

        hav = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        central_angle = 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))

        earth_radius = 6371000  # in meters
        distance = earth_radius * central_angle

        return distance


    def _bracketing_indexes(self, distance_m):
        points = self._cumulative

        if len(points) < 2:
            return 0, 0
        
        if distance_m < points[0]:
            return 0, 1

        if distance_m >= points[-1]:
            return len(self.points) - 2, len(self.points) - 1

        j = bisect_right(points, distance_m)

        return j - 1, j


    def slope_at(self, distance_m):
        #Calculate the slope gradient at a given position
        i, j = self._bracketing_indexes(distance_m)
        rise = self.points[j][2] - self.points[i][2]
        run = self._cumulative[j] - self._cumulative[i]
        return (rise / run) * 100, self.points[i][2], self.points[j][2], self._cumulative[i], self._cumulative[j] if run else 0.0


    def total_distance(self) -> float:
        #Calculate the total distance of the route
        return self._cumulative[-1] if self._cumulative else 0.0


    def elevation_stats(self) -> tuple[float, float]:
        #Return (elevation_gain, elevation_loss) in meters based on smoothed elevations
        gain = 0.0
        loss = 0.0
        for i in range(1, len(self.points)):
            delta = self.points[i][2] - self.points[i - 1][2]
            if delta > 0:
                gain += delta
            else:
                loss -= delta
        return gain, loss

    def geometry(self) -> list[dict]:
        #Route points shaped like the frontend RoutePoint: distance in km, grade in %
        out = []
        n = len(self.points)
        for i, (lat, lon, ele) in enumerate(self.points):
            if i < n - 1:
                run = self._cumulative[i + 1] - self._cumulative[i]
                grade = ((self.points[i + 1][2] - ele) / run * 100) if run > 1e-9 else 0.0
            else:
                grade = out[-1]["grade"] if out else 0.0
            out.append({
                "distance": round(self._cumulative[i] / 1000, 6),
                "elevation": round(ele, 2),
                "lat": lat,
                "lon": lon,
                "grade": round(grade, 3),
            })
        return out


    def __init__(self, points):
        self.points = points
        self._cumulative = self._compute_cumulative_distances()
        self._smooth_elevations(20.0)  # Smooth the elevations with a window of 20 meters


    def _compute_cumulative_distances(self):
        dist = [0.0]
        for i in range(1, len(self.points)):
            dist.append(dist[-1] + self.haversine_distance(self.points[i - 1], self.points[i]))
        return dist

    def position_at(self, distance_m):
        i, j = self._bracketing_indexes(distance_m)
        t = (distance_m - self._cumulative[i]) / (self._cumulative[j] - self._cumulative[i])
        lat = self.points[i][0] + t * (self.points[j][0] - self.points[i][0])
        lon = self.points[i][1] + t * (self.points[j][1] - self.points[i][1])
        ele = self.points[i][2] + t * (self.points[j][2] - self.points[i][2])
        return lat, lon, ele

    def heading_at(self, distance_m) -> float:
        i, j = self._bracketing_indexes(distance_m)
        lat1, lon1 = math.radians(self.points[i][0]), math.radians(self.points[i][1])
        lat2, lon2 = math.radians(self.points[j][0]), math.radians(self.points[j][1])
        d_lon = lon2 - lon1
        x = math.sin(d_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
        return math.atan2(x, y)  # bearing in radians

    def _smooth_elevations(self, window=20.0):
        smoothed = []
        left = 0
        right = 0
        n = len(self.points)
        for i in range(n):
            target = self._cumulative[i]
            while self._cumulative[left] < target - window / 2:
                left += 1
            while right < n - 1 and self._cumulative[right] < target + window / 2:
                right += 1
            elevations_in_window = [self.points[k][2] for k in range(left, right + 1)]
            smoothed.append(sum(elevations_in_window) / len(elevations_in_window))

        self.points = [(lat, lon, smoothed[i]) for i, (lat, lon, _) in enumerate(self.points)]


    def get_route_profile(self):
        #Get the route profile as a list of tuples (distance, elevation)
        elevation_points = [(self.points[i][2]) for i in range(len(self.points))]
        plt.plot(self._cumulative, elevation_points)
        plt.xlabel("Distance (m)")
        plt.ylabel("Elevation (m)")
        plt.title("Route Profile")
        plt.savefig("route_profile.png")


if __name__ == "__main__":
    # route = Route.get_route_from_gpx("../data/tour-de-friends.gpx")
    # print(route)
    print("Route class is ready for use.")