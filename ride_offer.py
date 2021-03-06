# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
from utility import convertToUtfIfNeeded

class RideOffer(ndb.Model): #ndb.Model
    driver_id = ndb.StringProperty()
    driver_name_lastname = ndb.StringProperty()
    driver_username = ndb.StringProperty()

    percorso = ndb.StringProperty() # mapping to percorso entry key (percorso.py)

    # TO DELETE: routes_info = ndb.PickleProperty()

    # TO DELETE: fermate_intermedie = ndb.StringProperty(repeated=True) # set of fermate intermedie
    # TO DELETE: percorsi_passeggeri_compatibili = ndb.StringProperty(repeated=True) # set of percorsi compatibili

    registration_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    active = ndb.BooleanProperty() # remains active for non-programmati

    start_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    disactivation_datetime = ndb.DateTimeProperty()

    time_mode = ndb.StringProperty()  # BOTTONE_ADESSO, BOTTONE_OGGI, BOTTONE_PROX_GIORNI, BOTTONE_PROGRAMMATO

    # only for regular rides
    programmato = ndb.BooleanProperty(default=False)
    programmato_giorni = ndb.IntegerProperty(repeated=True) # Monday is 0 and Sunday is 6
    # also used for prox. ggiorni mode
    # for time start_datetime is used

    average_distance = ndb.StringProperty()
    average_duration = ndb.StringProperty()

    distanza = ndb.IntegerProperty(repeated=True)

    def getDriverName(self):
        return convertToUtfIfNeeded(self.driver_name_lastname)

    def getPercorso(self):
        return convertToUtfIfNeeded(self.percorso)

    def getRouteEntry(self):
        from route import Route
        return Route.get_by_id(self.percorso)

    def getDepartingTime(self):
        import date_time_util as dtu
        #return dtu.formatTime(self.programmato_time)
        return dtu.formatTime(self.start_datetime.time())

    def getTimeMode(self):
        return convertToUtfIfNeeded(self.time_mode)

    def disactivate(self,  put=True):
        import date_time_util as dtu
        self.active = False
        self.disactivation_datetime = dtu.removeTimezone(dtu.nowCET())
        if put:
            self.put()

    def getAvgDistanceDuration(self):
        if self.average_distance is None:
            # initializing it the first time
            route = self.getRouteEntry()
            self.average_distance = route.average_distance
            self.average_duration = route.average_duration
            self.put()
        return self.average_distance, self.average_duration

    def getDescription(self, driver_info=True):
        import routing_util
        import params
        import date_time_util as dtu
        import person
        msg = []
        percorso = self.getPercorso()
        start_fermata, end_fermata = routing_util.decodePercorso(percorso)

        msg.append('*Partenza*: {}'.format(start_fermata))
        msg.append('*Arrivo*: {}'.format(end_fermata))

        if self.programmato:
            giorni = [params.GIORNI_SETTIMANA_FULL[i] for i in self.programmato_giorni]
            giorni_str = ', '.join(giorni)
            msg.append('*Ora partenza*: {}'.format(self.getDepartingTime()))
            msg.append('*Tipologia*: {}'.format(self.getTimeMode()))
            msg.append('*Ogni*: {}'.format(giorni_str))
        else:
            msg.append('*Quando*: {}'.format(self.getTimeMode()))
            msg.append('*Ora partenza*: {}'.format(self.getDepartingTime()))
            date_str = dtu.formatDate(self.start_datetime)
            if date_str == dtu.formatDate(dtu.nowCET()):
                date_str += ' (OGGI)'
            elif date_str == dtu.formatDate(dtu.tomorrow()):
                date_str += ' (DOMANI)'
            elif self.programmato_giorni: # PROX_GIORNI
                giorno_index = self.programmato_giorni[0]
                date_str += ' ({})'.format(params.GIORNI_SETTIMANA[giorno_index])
            msg.append('*Giorno partenza*: {}'.format(date_str))
        if driver_info:
            username = person.getPersonById(self.driver_id).getUsername()  # self.driver_username
            if username is None:
                from main import tell_admin
                tell_admin('❗ viaggio con driver_id {} non ha più username'.format(self.driver_id))
                username = '(username non più disponibile)'
            else:
                username = '@{}'.format(username)
            msg.append('*Autista*: {} {}'.format(self.getDriverName(), username))
            avg_distance, avg_duration = self.getAvgDistanceDuration()
            msg.append('*Distanza*: {}'.format(avg_distance))
            msg.append('*Durata*: {}'.format(avg_duration))
        return '\n'.join(msg)




def addRideOffer(driver, start_datetime, percorso,
                 time_mode, programmato, giorni):
    import date_time_util as dtu
    o = RideOffer(
        driver_id = driver.getId(),
        driver_name_lastname = driver.getFirstNameLastName(),
        driver_username=driver.getUsername(),
        start_datetime=start_datetime,
        percorso=percorso,
        registration_datetime = dtu.removeTimezone(dtu.nowCET()),
        active = True,
        time_mode = time_mode,
        programmato = programmato,
        programmato_giorni = giorni
    )
    o.put()
    return o

def filterAndSortOffersPerDay(offers):
    import params
    import date_time_util as dtu
    from datetime import timedelta

    result = [[],[],[],[],[],[],[]]
    today = dtu.getWeekday()
    now_dt = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
    now_time = now_dt.time()
    for o in offers:
        if o.programmato:
            for g in o.programmato_giorni:
                # exclude those of today which have already happened
                if g != today or o.start_datetime.time() > now_time: #o.programmato_time > now_time:
                    result[g].append(o)
        elif o.start_datetime > now_dt:
            g = dtu.getWeekday(o.start_datetime)
            result[g].append(o)
    for results_days in result:
        results_days.sort(key=lambda x: x.getDepartingTime())
    return result

def getActiveRideOffersQry():
    import params
    import date_time_util as dtu
    from datetime import timedelta
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(
                    minutes=params.TIME_TOLERANCE_MIN)
            )
        )
    )
    return qry


def getActiveRideOffersCountInWeek():
    offers = getActiveRideOffersQry().fetch()
    offers_list_per_day = filterAndSortOffersPerDay(offers)
    count = sum([len(d) for d in offers_list_per_day])
    return count

def getRideOfferInsertedLastDaysQry(days):
    import date_time_util as dtu
    from datetime import timedelta
    return RideOffer.query(
        RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(days=days)
    )


'''
def getActiveRideOffersProgrammatoQry():
    return RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.programmato == True,
        )
    )
'''


def getActiveRideOffersDriver(driver_id):
    import params
    import date_time_util as dtu
    from datetime import timedelta
    now_with_tolerance = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.driver_id == driver_id,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= now_with_tolerance
            )
        )
    ).order(RideOffer.start_datetime)
    return qry.fetch()

def getActiveRideOffersSortedPerDay(percorso_passeggero):
    from route import Route
    import params
    import date_time_util as dtu
    from datetime import timedelta

    nowWithTolerance = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)

    qry_routes = Route.query(
        Route.percorsi_passeggeri_compatibili == percorso_passeggero,
    )
    percorsi_compatibili = [r.getPercorso() for r in qry_routes.fetch()]

    if percorsi_compatibili:
        qry_rides = RideOffer.query(
            ndb.AND(
                RideOffer.percorso.IN(percorsi_compatibili),
                RideOffer.active == True,
                ndb.OR(
                    RideOffer.programmato == True,
                    RideOffer.start_datetime >= nowWithTolerance
                )
            )
        )
        offers = qry_rides.fetch()
    else:
        offers = []
    return filterAndSortOffersPerDay(offers)

def getActiveRideOffers():
    import params
    import date_time_util as dtu
    from datetime import timedelta

    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
                # might be redundant as the filter is also applied afterwards
            )
        )
    )
    offers = qry.fetch()
    return offers

