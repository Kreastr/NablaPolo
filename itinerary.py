from google.appengine.ext import ndb
import math
import operator
import logging
import person


#CITIES
CITY_TRENTO = 'Trento'
CITY_CALTANISSETTA = 'Caltanissetta'

CITIES = (CITY_TRENTO, CITY_CALTANISSETTA)

# http://overpass-turbo.eu/
# node["highway"="bus_stop"]({{bbox}});

#BUS STOPS TRENTO
TN_FS = ('Stazione FS', 46.0725463, 11.1199586, 'FS')
TN_Aquila = ("Venezia Port'Aquila", 46.0695135, 11.1278832, 'P_AQ')
TN_MesianoIng = ("MESIANO Fac. Ingegneria", 46.0671184, 11.1394574, 'MES_ING')
TN_Povo_Valoni = ("POVO Valoni", 46.0655767, 11.1462844, 'PV_VA')
TN_Povo_Sommarive = ("POVO Sommarive", 46.0654307, 11.1503973, 'PV_SO')
TN_Povo_PoloScientifico = ("POVO Polo Scientifico", 46.0671854, 11.1504241, 'PV_SC')
TN_Povo_Manci = ("POVO Piazza Manci", 46.0659831, 11.1545571, 'PV_M')
TN_Rosmini_SMM = ('Rosmini S.Maria Maggiore', 46.0678403, 11.1188594, 'RSM')
TN_Travai = ('Travai', 46.0645194, 11.1209105, 'Tra')
TN_Cavallegggeri = ("3 Nov. Ponte Cavalleggeri", 46.0592422, 11.126718, 'CAV')
TN_Questura = ("Verona Questura", 46.0457542, 11.1309265, 'QSTR')

#new entry
TN_Pergine_FS = ("Pergine FS", 46.0634661, 11.2315599, 'PER_FS')
# mattarello 46.0114635 / 11.1303024
#Trento Nord - Zona Commerciale 46.090066,11.113395

FERMATA_TRENTO = TN_Aquila[0]
FERMATA_POVO = TN_Povo_PoloScientifico[0]


#BUS STOPS CALTANISSETTA
CL_FS = ('Stazione FS', 37.4885123, 14.0577765, 'FS')
CL_Cefpas = ('Cefpas', 37.490577, 14.0290256, 'CEFPAS')

CITY_BUS_STOPS = {
    CITY_TRENTO: (
        TN_Povo_Valoni,
        TN_Povo_Sommarive,
        TN_Povo_PoloScientifico,
        TN_Povo_Manci,
        TN_FS,
        TN_Aquila,
        TN_MesianoIng,
        TN_Rosmini_SMM,
        TN_Travai,
        TN_Cavallegggeri,
        TN_Questura,
        TN_Pergine_FS
    ),
    CITY_CALTANISSETTA: (
        CL_FS,
        CL_Cefpas
    )
}

MAX_CLUSTER_DISTANCE = 0.5 #km

class BusStop(ndb.Model):
    city = ndb.StringProperty()
    name = ndb.StringProperty()
    short_name = ndb.StringProperty()
    location = ndb.GeoPtProperty()
    cluster = ndb.StringProperty(repeated=True)

def getKeyFromBusStop(bus_stop):
    return bus_stop.city + " " + bus_stop.name

def getKey(cityName, bsName):
    return cityName + " " + bsName

def getBusStop(cityName, bsName):
    key = getKey(cityName, bsName)
    return ndb.Key(BusStop, key).get()

def initBusStops():
    for city_key in CITY_BUS_STOPS:
        for bs_lat_lon in CITY_BUS_STOPS[city_key]:
            bs_name = bs_lat_lon[0]
            key = getKey(city_key,bs_name)
            bs = ndb.Key(BusStop, key).get()
            if (bs==None):
                bs = BusStop.get_or_insert(key)
                bs.populate(city=city_key,name=bs_lat_lon[0],location=ndb.GeoPt(bs_lat_lon[1], bs_lat_lon[2]), short_name=bs_lat_lon[3])
            bs.cluster = [bs_name]
            bs.put()
    for city_key in CITY_BUS_STOPS:
        city_busstops = CITY_BUS_STOPS[city_key]
        for stop_i in city_busstops:
            stop_i_name = stop_i[0]
            bs_i = getBusStop(city_key, stop_i_name)
            loc_i=ndb.GeoPt(stop_i[1], stop_i[2])
            for stop_j in city_busstops:
                stop_j_name = stop_j[0]
                if (stop_i_name==stop_j_name):
                    continue
                loc_j=ndb.GeoPt(stop_j[1], stop_j[2])
                dst = HaversineDistance(loc_i, loc_j)
                if (dst<=MAX_CLUSTER_DISTANCE):
                    bs_i.cluster.append(stop_j_name)
                    bs_i.put()


def HaversineDistance(loc1, loc2):
    """Method to calculate Distance between two sets of Lat/Lon."""
    lat1 = loc1.lat
    lon1 = loc1.lon
    lat2 = loc2.lat
    lon2 = loc2.lon
    earth = 6371 #Earth's Radius in Kms.

    #Calculate Distance based in Haversine Formula
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = earth * c
    return d

MAX_DISTANCE = 1.0 #km

def getBusStopLocation(city, bs_name):
    bs = BusStop.query(BusStop.city==city, BusStop.name==bs_name).get()
    return bs.location

def matchDriverAndPassengerEnd(driver, passenger, usePassengerLocation=True):
    bs_end_d = getBusStop(driver.last_city, person.getDestination(driver))
    passengerEnd = person.getDestination(passenger) if usePassengerLocation else passenger.bus_stop_end
    bs_end_p = getBusStop(passenger.last_city, passengerEnd)
    if (bs_end_d is None or bs_end_p is None):
        return False
    return matchClusterLocation(bs_end_d, bs_end_p)

def matchDriverAndPassengerStart(driver, passenger, usePassengerLocation=True):
    bs_start_d = getBusStop(driver.last_city, driver.location)
    passengerStart = passenger.location if usePassengerLocation else passenger.bus_stop_start
    bs_start_p = getBusStop(passenger.last_city, passengerStart)
    if (bs_start_d is None or bs_start_p is None):
        return False
    return matchClusterLocation(bs_start_d, bs_start_p)

def matchDriverMidPointsAndPassengerStart(driver, passenger, usePassengerLocation=True):
    midPoints = person.getMidPoints(driver)
    if not midPoints:
        return False
    passengerStart = passenger.location if usePassengerLocation else passenger.bus_stop_start
    bs_start_p = getBusStop(passenger.last_city, passengerStart)
    for md in midPoints:
        bs_start_d = getBusStop(driver.last_city, md)
        if bs_start_d is not None and bs_start_p is not None and matchClusterLocation(bs_start_d, bs_start_p):
            return True
    return False

def matchDriverMidPointsAndPassengerEnd(driver, passenger, usePassengerLocation=True):
    midPoints = person.getMidPoints(driver)
    if not midPoints:
        return False
    passengerEnd = person.getDestination(passenger) if usePassengerLocation else passenger.bus_stop_end
    bs_end_p = getBusStop(passenger.last_city, passengerEnd)
    for md in midPoints:
        bs_end_d = getBusStop(driver.last_city, md)
        if bs_end_d is not None and bs_end_p is not None and matchClusterLocation(bs_end_d, bs_end_p):
            return True
    return False


def matchDriverAndPassenger(driver, passenger):
    return ( matchDriverAndPassengerStart(driver, passenger) or
             matchDriverMidPointsAndPassengerStart(driver, passenger)) and\
           (matchDriverAndPassengerEnd(driver, passenger) or
            matchDriverMidPointsAndPassengerEnd(driver, passenger))

def matchDriverAndPotentialPassenger(driver, passenger):
    return ( matchDriverAndPassengerStart(driver, passenger, False) or
             matchDriverMidPointsAndPassengerStart(driver, passenger, False)) and\
           (matchDriverAndPassengerEnd(driver, passenger, False) or
            matchDriverMidPointsAndPassengerEnd(driver, passenger, False))


def matchClusterLocation(loc1, loc2):
    #return loc1.name == loc2.name or loc2.name in loc1.cluster
    return loc2.name in loc1.cluster


def getClosestBusStops(loc_point, exclude_points, person, max_distance=MAX_DISTANCE, trim=True):
    result = []
    first = True
    for bs in BusStop.query():
        if bs.name in exclude_points:
            continue
        dst = HaversineDistance(bs.location, loc_point)
        if (dst<=max_distance):
            result.append([bs.name, dst])
            if first:
                first = False
                person.last_city = bs.city
                person.put()
    result = sort_table(result, 1)
    #logging.debug(result)
    if trim:
        result = result[:2]
    return column(result,0)

def getOtherBusStops(person):
    result = []
    first = True
    for bs in BusStop.query(BusStop.city==person.last_city):
        if (bs.name not in [person.bus_stop_start,person.bus_stop_end] and
            bs.name not in [person.bus_stop_mid_going] and
            bs.name not in [person.bus_stop_mid_back]):
            result.append(bs.name)
    return result

def sort_table(table, col=0):
    return sorted(table, key=operator.itemgetter(col))

def column(matrix, i):
    return [row[i] for row in matrix]



