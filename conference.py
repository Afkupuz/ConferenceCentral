#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""
from __future__ import division
__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime

import operator
import endpoints
import collections

from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import *

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import *

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER_"
FEATURED_SPEAKER_TPL = ('Featured speaker: %s\nSessions: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

ops = {'==' : operator.eq,
       '='  : operator.eq,
       '!=' : operator.ne,
       '<=' : operator.le,
       '>=' : operator.ge,
       '>'  : operator.gt,
       '<'  : operator.lt
       }

FIELDS = {
        'CITY': 'city',
        'TOPIC': 'topics',
        'MONTH': 'month',
        'MAX_ATTENDEES': 'maxAttendees',
        }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESS_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    )

SESS_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

SESS_GET_TYPE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
)

SESS_GET_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)

SESS_POST_WISHLIST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SESS_GET_WISHLIST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SPEC_POST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    value=messages.IntegerField(1),
    operator=messages.StringField(2))

SESS_POST_DOUBLE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    time=messages.StringField(2),
    sess_type=messages.StringField(3))

FEAT_GET_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1))

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        #organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        #profiles = ndb.get_multi(organisers)
        
        # put display names in a dict for easier fetching
        #names = {}
        #for profile in profiles:
        #    names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        #return ConferenceForms(
         #       items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
          #      conferences]
        #)
        return ConferenceForms(items=[self._copyConferenceToForm(conf, "Why_doesnt_this_work?") for conf in conferences])
        

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground"""
        q = Conference.query()
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        q = q.filter(Conference.city=="London")
        q = q.filter(Conference.topics=="Medical Innovations")
        q = q.filter(Conference.month==6)

        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") for conf in q]
        )

# - - - Session objects - - - - - - - - - - - - - - - - - - -

    def _createSessionObject(self, request):
        """ Create new sesssion """
        # check login
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        # check for required name
        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")
        # check required key
        wsck = request.websafeConferenceKey
        if not wsck:
            raise endpoints.BadRequestException("websafeConferenceKey required")
        # get conference and check if it exists
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException("No conference by that id")
        # check ownership
        user_id = getUserId(user)
        conf_id = conf.organizerUserId
        if user_id != conf_id:
            raise endpoints.UnauthorizedException("Unauthorized access")
        # copy data
        data = {field.name: getattr(request, field.name)
            for field in request.all_fields()}
        # clear key feild
        del data['websafeKey']

        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()
            if not conf.startDate <= data['date'] <= conf.endDate:
                raise endpoints.BadRequestException(
                    'Session date does not match conference date.')
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'][:10], "%H%M").time()
            if not data['startTime']:
                raise endpoints.BadRequestException(
                    'Please use military time')

        if data['typeOfSession']:
            data['typeOfSession'] = str(data['typeOfSession'])
        else:
            data['typeOfSession'] = str(TypeOfSession.Not_Specified)

        # allocate new Session ID with Profile key as parent
        s_id = Session.allocate_ids(size=1, parent=conf.key)[0]
        # make Session key from ID
        s_key = ndb.Key(Session, s_id, parent=conf.key)
        data['key'] = s_key

        # create Session & return (modified) ConferenceForm
        hold = Session(**data)
        the_key = hold.key.urlsafe()
        hold.put()


        taskqueue.add(
            params={'websafeConferenceKey': wsck,
            'websafeSessionKey': the_key},
            url='/tasks/set_featured_speaker'
        )
    
        return request

    @endpoints.method(SessionForm, SessionForm,
        path='conference/newsession',
        http_method='POST', name='createSession')
    def createSession(self, request):
        """ create new session """
        return self._createSessionObject(request)

    def _copySessionToForm(self, sess):
        sf = SessionForm()
        for field in sf.all_fields():
            # convert to strings
            if hasattr(sess, field.name):
                # convert date
                if field.name.endswith('date'):
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                # convert time    
                elif field.name.endswith('startTime'):
                    setattr(sf, field.name, str(getattr(sess, field.name)))
                # convert enum
                elif field.name.endswith('typeOfSession'):
                    setattr(sf, field.name, getattr(
                        TypeOfSession, getattr(sess, field.name)))
                # finish
                else:
                    setattr(sf, field.name, getattr(sess, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, sess.key.urlsafe())
        sf.check_initialized()
        return sf


    @endpoints.method(SESS_GET_REQUEST, SessionForms,
        path='conference/{websafeConferenceKey}/session',
        http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """ Return conference sessions """
        # get query with filter for matching keys
        q = Session.query().filter(
                Session.websafeConferenceKey == request.websafeConferenceKey)
        # order by start time
        q = q.order(Session.startTime)
        # retrieve data
        sessions = q.fetch()
        # return a form
        return SessionForms(
            sessions=[self._copySessionToForm(sess) for sess in sessions])

    @endpoints.method(SESS_GET_SPEAKER, SessionForms,
        path='session/{websafeSpeakerKey',
        http_method='GET', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """ Return sessions by speaker """
        # query and filter by speaker name
        q = Session.query().filter(Session.speakerKeys == request.websafeSpeakerKey)
        # ordy by start time
        q = q.order(Session.startTime)
        # retrieve data
        sessions = q.fetch()
        # return form
        return SessionForms(
            sessions=[self._copySessionToForm(sess) for sess in sessions])

    @endpoints.method(SESS_GET_TYPE, SessionForms,
        path='session/{typeOfSession}',
        http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """ Return sessions by type """
        # query and filter by speaker name
        q = Session.query().filter(Session.typeOfSession == request.typeOfSession)
        # ordy by start time
        q = q.order(Session.startTime)
        sessions = q.fetch()
        # return form
        return SessionForms(
            sessions=[self._copySessionToForm(sess) for sess in sessions]) 

# - - - Speaker objects - - - - - - - - - - - - - - - - - - -

    def _createSpeakerObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required.')
        # 'name' is a required field
        if not request.name:
            raise endpoints.BadRequestException("Speaker name required")
        # copy data to dict
        data = {field.name: getattr(request, field.name)
            for field in request.all_fields()}
        del data['websafeKey']
        # store new speaker
        Speaker(**data).put()

        return request

    def _copySpeakerToForm(self, speaker):
        """ speaker info in form format """
        # get form
        sf = SpeakerForm()
        # fill in feilds
        for field in sf.all_fields():
            # generic fields
            if hasattr(speaker, field.name):
                setattr(sf, field.name, getattr(speaker, field.name))
            # special field
            elif field.name == 'websafeKey':
                setattr(sf, field.name, speaker.key.urlsafe())
        # initialize
        sf.check_initialized()
        return sf

    @endpoints.method(SpeakerForm, SpeakerForm,
        path='speaker',
        http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """ Create new speaker object """
        return self._createSpeakerObject(request)

    @endpoints.method(message_types.VoidMessage, SpeakerForms,
        path='speakers',
        http_method='GET', name='getSpeakers')
    def getSpeakers(self, request):
        """ retrieve all speakers by name """
        # query speakers and order by name
        speakers = Speaker.query().order(Speaker.name)
        return SpeakerForms(
            speakers=[self._copySpeakerToForm(speak) for speak in speakers])

# - - - Wishlist objects - - - - - - - - - - - - - - - - - - -

    @ndb.transactional (xg=True)
    def _sessionWishList(self, request, to_add=True):
        # return value flaggs completed or not
        retval = False
        # get user profile
        prof = self._getProfileFromUser()
        # get session key
        sess_Key = request.websafeSessionKey
        sess = ndb.Key(urlsafe=sess_Key).get()

        # check for session
        if not sess:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % sess_Key)

        # add or remove session
        if to_add:
            # check for pre-existing session
            if sess_Key in prof.sessionWishlistKeys:
                raise ConflictException("You have already added this session")
            # add session to dic
            prof.sessionWishlistKeys.append(sess_Key)
            # return true
            retval = True
        else:
            # check for pre-existing session
            if sess_Key in prof.sessionWishlistKeys:
                # remove session
                prof.sessionWishlistKeys.remove(sess_Key)
                # return true
                retval = True
            else:
                raise ConflictException("This session is not in your wishlist")
                retval = False

        # save profile changes
        prof.put()
        # return boolean
        return BooleanMessage(data=retval)


    @endpoints.method(SESS_POST_WISHLIST, BooleanMessage,
        path='session/{websafeSessionKey}',
        http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """ Add session to wishlist """
        # pass no value for to_add because it is set to true by default
        return self._sessionWishList(request)

    @endpoints.method(SESS_POST_WISHLIST, BooleanMessage,
        path='session/{websafeSessionKey}',
        http_method='DELETE', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        """ Remove session to wishlist """
        # pass false value for to_add because it is set to true by default
        return self._sessionWishList(request, to_add=False)

    @endpoints.method(SESS_GET_WISHLIST, SessionForms,
            path='wishlist/{websafeConferenceKey}',
            name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """Get sessions in user wishlist """
        # get profile info
        prof = self._getProfileFromUser()
        # get wishlist keys and fined sessions
        wish_keys = [ndb.Key(urlsafe=s) for s in prof.sessionWishlistKeys]
        sessions = ndb.get_multi(wish_keys)
        # return sessions in form
        return SessionForms(
            sessions=[self._copySessionToForm(wishes) for wishes in sessions])


# - - - Additional queries objects - - - - - - - - - - - - - - - - - - -

#fetch speakers by rating
#fetch conferences by % full

    @endpoints.method(SPEC_POST, SpeakerForms,
        path='getSpeakerByRating',
        http_method="GET", name='getSpeakerByRating')
    def getSpeakerByRating(self, request):
        """ get speakers based on rating """
        # query speakers
        q = Speaker.query()
        
        try:
            op = OPERATORS[request.operator]
        except KeyError:
            raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # only one value to filter by so we don't 
            # have to worry about too many inequality filters

            # apply filters
            #q = q.filter("rating", op, request.value)

            # fetch results
            formatted_query = ndb.query.FilterNode("rating", op, request.value)
            q = q.filter(formatted_query)
            #speak = q.fetch()

        return SpeakerForms(
            speakers=[self._copySpeakerToForm(speak) for speak in q])

    @endpoints.method(SPEC_POST, ConferenceForms,
        path='getPercentFullConf',
        http_method='POST', name='getPercentFullConf')
    def getPercentFullConf(self, request):
        """ Get conferences by percent full """
        # get conferences
        conf = Conference.query().fetch()
        # set empty array for conferences
        conf_array = []
        percent_array = []
        # give value a variable
        value = request.value
        # try to set operator
        try:
            o = OPERATORS[request.operator]
            # translate string operator to python operator using import operator
            op = ops[o]
        except KeyError:
            raise endpoints.BadRequestException("Filter contains invalid field or operator.")
        # test percent full
        for c in conf:
            sa = c.seatsAvailable
            ts = c.maxAttendees
            #print str(sa) + " , " + str(ts)
            if ts == 0:
                percent = 0
            else:
                percent = sa/ts*100
            # add those that pass to new array
            #print str(percent)
            if op(percent, value):
                conf_array.append(c)
                percent_array.append(percent)
        # sort array by name
        sorted(conf_array, key=lambda conference: conference.name)
        # return conferences added to the array
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                confs, "percent return") for confs in conf_array])

    @endpoints.method(SESS_POST_DOUBLE, SessionForms,
        path='conference/{websafeConferenceKey/sessions/double',
        http_method='POST', name='getDoubleQuerySession')
    def getDoubleQuerySession(self, request):
        # empty dic for sessions
        result = []
        # query sessions        
        q = Session.query()
        # filter by time
        formatedTime = datetime.strptime(request.time[:10], "%H%M").time()
        q = q.filter(Session.startTime < formatedTime)
        # sort by time
        q = q.order(Session.startTime)
        # fetch results
        sessions = q.fetch()
        # use python to weed out conference types
        for sess in sessions:
            if sess.typeOfSession == request.sess_type:
                result.append(sess)
        # return result of sort
        return SessionForms(
            sessions=[self._copySessionToForm(sess) for sess in result])

# - - - Featured speaker - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheSpeaker(request):
        """ Memcache speaker announcement """
        print 'got to cache'
        # set empty list
        spk_array = []
        # get all sessions in current conference
        wsck = request.get('websafeConferenceKey')
        sessions = Session.query().filter(Session.websafeConferenceKey == wsck)
        # get created session
        wssk = request.get('websafeSessionKey')
        newSess = ndb.Key(urlsafe=wssk).get()
        
        # build array of sessions that share speakers
        for sess in sessions:
            # make sure that we dont count the recently created session
            if sess.key != newSess.key:
                #check for keys
                if sess.speakerKeys:
                    # for each speaker key in all sessions
                    for spk_key in sess.speakerKeys:
                        # for each speaker in the recent session
                        for keys in newSess.speakerKeys:
                            # compare keys and add session if they match
                            if spk_key == keys:
                                if sess in spk_array:
                                    print 'there already'
                                else:
                                    spk_array.append(sess)
                                    speaker = ndb.Key(urlsafe=spk_key).get()

        if len(spk_array) > 0:
            # add created session that was left out if others were found
            spk_array.append(newSess)
            # set featured speaker
            featured_speaker = FEATURED_SPEAKER_TPL % (
                speaker.name,
                ', '.join(s.name for s in spk_array)
            )
            # setting the memcache key allows for conference unique keys
            memcache.set(
                MEMCACHE_FEATURED_SPEAKER_KEY + wsck, featured_speaker)
        else:
            featured_speaker = ""

        return featured_speaker


    @endpoints.method(FEAT_GET_SPEAKER, StringMessage,
            path='conference/{websafeConferenceKey}/feature',
            name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Reaturn Featured Speaker and Sessions from memcache."""
        wsck = request.websafeConferenceKey
        memcache_key = MEMCACHE_FEATURED_SPEAKER_KEY + wsck
        return StringMessage(data=memcache.get(memcache_key) or "")
















api = endpoints.api_server([ConferenceApi]) # register API
