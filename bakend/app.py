from flask import Flask, request, jsonify
import requests
import os
import math

app = Flask(__name__)

# ==========================================================
# GEOAPIFY API KEY
# ==========================================================
# Set your API key as an environment variable:
#
# Windows:
# set GEOAPIFY_API_KEY=YOUR_API_KEY
#
# Linux / GitHub Codespaces:
# export GEOAPIFY_API_KEY=YOUR_API_KEY
#
# Do NOT put the real API key directly in this file.

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

# Geoapify Places API
GEOAPIFY_URL = "https://api.geoapify.com/v2/places"


# ==========================================================
# HAVERSINE DISTANCE
# ==========================================================

def calculate_distance(lat1, lon1, lat2, lon2):

    earth_radius = 6371000  # meters

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    difference_lat = math.radians(lat2 - lat1)
    difference_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(difference_lat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(difference_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# ==========================================================
# INDUSTRY RISK
# ==========================================================

def calculate_risk(industry_type, distance_meters):

    industry = industry_type.lower()

    # ------------------------------------------
    # Base risk according to industry
    # ------------------------------------------

    high_risk_industries = [
        "chemical",
        "petroleum",
        "oil",
        "refinery",
        "steel",
        "metal",
        "cement",
        "power",
        "waste",
        "landfill",
        "mining",
        "quarry"
    ]

    medium_risk_industries = [
        "textile",
        "food",
        "brewery",
        "automotive",
        "construction",
        "warehouse",
        "engineering",
        "machine",
        "manufacturing"
    ]

    if any(
        word in industry
        for word in high_risk_industries
    ):

        score = 70

    elif any(
        word in industry
        for word in medium_risk_industries
    ):

        score = 45

    else:

        score = 25

    # ------------------------------------------
    # Distance factor
    # ------------------------------------------

    distance_km = distance_meters / 1000

    if distance_km <= 1:

        score += 30

    elif distance_km <= 3:

        score += 20

    elif distance_km <= 5:

        score += 10

    # Maximum score
    score = min(score, 100)

    # ------------------------------------------
    # Risk level
    # ------------------------------------------

    if score >= 70:

        risk = "HIGH"

    elif score >= 40:

        risk = "MEDIUM"

    else:

        risk = "LOW"

    return risk, score


# ==========================================================
# GEOAPIFY SEARCH
# ==========================================================

def search_nearby_industries(
    latitude,
    longitude,
    radius
):

    params = {

        "categories":
            "production.factory,industrial",

        "filter":
            f"circle:{longitude},{latitude},{radius}",

        "bias":
            f"proximity:{longitude},{latitude}",

        "limit":
            50,

        "apiKey":
            GEOAPIFY_API_KEY
    }

    response = requests.get(
        GEOAPIFY_URL,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            "Geoapify API Error: "
            + str(response.status_code)
            + " "
            + response.text
        )

    return response.json()


# ==========================================================
# FIND INDUSTRY TYPE
# ==========================================================

def get_industry_type(properties):

    categories = properties.get(
        "categories",
        []
    )

    if len(categories) > 0:

        return categories[-1]

    return "industrial"


# ==========================================================
# NEARBY INDUSTRIES API
# ==========================================================

@app.route(
    "/nearby-industries",
    methods=["POST"]
)
def nearby_industries():

    try:

        # ------------------------------------------
        # API KEY CHECK
        # ------------------------------------------

        if not GEOAPIFY_API_KEY:

            return jsonify({

                "success": False,

                "error":
                    "Geoapify API key is not configured."

            }), 500

        # ------------------------------------------
        # GET JSON
        # ------------------------------------------

        data = request.get_json()

        if not data:

            return jsonify({

                "success": False,

                "error":
                    "JSON data is required."

            }), 400

        # ------------------------------------------
        # GET LATITUDE
        # ------------------------------------------

        if "latitude" not in data:

            return jsonify({

                "success": False,

                "error":
                    "Latitude is required."

            }), 400

        # ------------------------------------------
        # GET LONGITUDE
        # ------------------------------------------

        if "longitude" not in data:

            return jsonify({

                "success": False,

                "error":
                    "Longitude is required."

            }), 400

        latitude = float(
            data["latitude"]
        )

        longitude = float(
            data["longitude"]
        )

        # ------------------------------------------
        # SEARCH RADIUS
        # ------------------------------------------

        radius = int(
            data.get(
                "radius",
                5000
            )
        )

        # ------------------------------------------
        # VALIDATION
        # ------------------------------------------

        if latitude < -90 or latitude > 90:

            return jsonify({

                "success": False,

                "error":
                    "Invalid latitude."

            }), 400

        if longitude < -180 or longitude > 180:

            return jsonify({

                "success": False,

                "error":
                    "Invalid longitude."

            }), 400

        if radius <= 0:

            return jsonify({

                "success": False,

                "error":
                    "Radius must be greater than 0."

            }), 400

        # ------------------------------------------
        # CALL GEOAPIFY
        # ------------------------------------------

        geoapify_data = search_nearby_industries(
            latitude,
            longitude,
            radius
        )

        features = geoapify_data.get(
            "features",
            []
        )

        nearby_sources = []

        # ==================================================
        # PROCESS EVERY INDUSTRY
        # ==================================================

        for feature in features:

            properties = feature.get(
                "properties",
                {}
            )

            # ------------------------------------------
            # Factory coordinates
            # ------------------------------------------

            factory_lat = properties.get(
                "lat"
            )

            factory_lon = properties.get(
                "lon"
            )

            if (
                factory_lat is None
                or
                factory_lon is None
            ):
                continue

            # ------------------------------------------
            # Factory name
            # ------------------------------------------

            factory_name = properties.get(
                "name",
                "Unnamed Factory"
            )

            # ------------------------------------------
            # Address
            # ------------------------------------------

            address = properties.get(
                "formatted",
                "Address unavailable"
            )

            # ------------------------------------------
            # Industry type
            # ------------------------------------------

            industry_type = get_industry_type(
                properties
            )

            # ------------------------------------------
            # Calculate distance
            # ------------------------------------------

            distance = calculate_distance(
                latitude,
                longitude,
                factory_lat,
                factory_lon
            )

            # ------------------------------------------
            # Risk
            # ------------------------------------------

            risk, risk_score = calculate_risk(
                industry_type,
                distance
            )

            # ------------------------------------------
            # Add result
            # ------------------------------------------

            nearby_sources.append({

                "name":
                    factory_name,

                "industry_type":
                    industry_type,

                "latitude":
                    factory_lat,

                "longitude":
                    factory_lon,

                "address":
                    address,

                "distance_m":
                    round(distance, 2),

                "distance_km":
                    round(
                        distance / 1000,
                        3
                    ),

                "risk_score":
                    risk_score,

                "risk":
                    risk
            })

        # ==================================================
        # SORT BY DISTANCE
        # ==================================================

        nearby_sources.sort(
            key=lambda x:
            x["distance_m"]
        )

        # ==================================================
        # OVERALL RISK
        # ==================================================

        if len(nearby_sources) == 0:

            overall_risk = "LOW"

        elif any(
            source["risk"] == "HIGH"
            for source in nearby_sources
        ):

            overall_risk = "HIGH"

        elif any(
            source["risk"] == "MEDIUM"
            for source in nearby_sources
        ):

            overall_risk = "MEDIUM"

        else:

            overall_risk = "LOW"

        # ==================================================
        # FINAL RESPONSE
        # ==================================================

        return jsonify({

            "success":
                True,

            "input_location": {

                "latitude":
                    latitude,

                "longitude":
                    longitude
            },

            "search_radius_m":
                radius,

            "search_radius_km":
                round(
                    radius / 1000,
                    2
                ),

            "nearby_factory_count":
                len(nearby_sources),

            "overall_risk":
                overall_risk,

            "nearby_sources":
                nearby_sources
        })

    # ======================================================
    # ERROR HANDLING
    # ======================================================

    except ValueError:

        return jsonify({

            "success": False,

            "error":
                "Latitude, longitude and radius must be numbers."

        }), 400

    except requests.exceptions.Timeout:

        return jsonify({

            "success": False,

            "error":
                "Geoapify request timed out."

        }), 504

    except requests.exceptions.RequestException as error:

        return jsonify({

            "success": False,

            "error":
                "Unable to connect to Geoapify.",
           
            "details":
                str(error)

        }), 502

    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500


# ==========================================================
# HOME / STATUS
# ==========================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "project":
            "Factory and Industry Risk Detection",

        "status":
            "Backend running",

        "api":
            "Geoapify",

        "endpoint":
            "/nearby-industries",

        "method":
            "POST"
    })


# ==========================================================
# START SERVER
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
