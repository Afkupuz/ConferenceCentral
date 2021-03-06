#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT

# added wishlist array 
class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='Not_Specified')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)
    sessionWishlistKeys = ndb.StringProperty(repeated=True)

class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)

# added wishlist array 
class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)
    sessionWishlistKeys = messages.StringField(5, repeated=True)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty() # TODO: do we need for indexing like Java?
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6) #DateTimeField()
    month           = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate         = messages.StringField(10) #DateTimeField()
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)

class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)

class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)

# - - -Final project addons - - - - - - - - - - - - - - - - - - - - - - - - - - -

# added wishlist to Profile and ProfileForm

# define class for sessions and make it a child of Conference
class Session(ndb.Model):
    """ Session Entity Object """
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty()
    speakerKeys     = ndb.StringProperty(repeated=True)
    duration        = ndb.IntegerProperty()
    typeOfSession   = ndb.StringProperty(default='Not_Specified')
    date            = ndb.DateProperty()
    startTime       = ndb.TimeProperty()
    websafeConferenceKey = ndb.StringProperty(required=True)

# define a session form and a child of conferenceform
class SessionForm(messages.Message):
    """ Session query from message form """
    name            = messages.StringField(1)
    highlights      = messages.StringField(2)
    speakerKeys     = messages.StringField(3, repeated=True)
    duration        = messages.IntegerField(4, variant=messages.Variant.INT32)
    typeOfSession   = messages.EnumField('TypeOfSession', 5)
    date            = messages.StringField(6)
    startTime       = messages.StringField(7)
    websafeKey      = messages.StringField(8)
    websafeConferenceKey = messages.StringField(9)

# for multiple returns
class SessionForms(messages.Message):
    """ Session multiple query form """
    sessions = messages.MessageField(SessionForm, 1, repeated=True)

# enum for session types
class TypeOfSession(messages.Enum):
    """ enumeration for session types """
    Not_Specified = 1
    Keynote = 2
    Lecture = 3
    Workshop = 4
    Demonstration = 5

# define entity class for speakers
class Speaker(ndb.Model):
    """ Speaker Entity Object """
    name            = ndb.StringProperty(required=True)
    organization    = ndb.StringProperty()
    bio             = ndb.StringProperty()
    rating          = ndb.IntegerProperty()

# define form for speaker
class SpeakerForm(messages.Message):
    """ Speaker query from messages form """
    name            = messages.StringField(1)
    organization    = messages.StringField(2)
    bio             = messages.StringField(3)
    rating          = messages.IntegerField(4)
    websafeKey      = messages.StringField(5)

# for multiple returns
class SpeakerForms(messages.Message):
    """ Speaker multiple query form """
    speakers = messages.MessageField(SpeakerForm, 1, repeated=True)
