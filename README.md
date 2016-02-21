# Conference Central
App Engine application for the Udacity training course.

## The Project
1. Install Google App Engine - [App Engine][1]
2. Clone the fullstack-nanodegree repository  
3. Add Sessions and endpoints:  
<ul>
  <li> getConferenceSessions(websafeConferenceKey) -- Given a conference, return all sessions </li>
  <li> getConferenceSessionsByType(websafeConferenceKey, typeOfSession) Given a conference, return all sessions of a specified type (eg lecture, keynote, workshop) </li>
  <li> getSessionsBySpeaker(speaker) -- Given a speaker, return all sessions given by this particular speaker, across all conferences </li>
  <li> createSession(SessionForm, websafeConferenceKey) -- open only to the organizer of the conference </li>
</ul>
4. Add user wishlist and endpoints:
  *	addSessionToWishlist(SessionKey) -- adds the session to the user's list of sessions they are interested in attending
  *	getSessionsInWishlist() -- query for all the sessions in a conference that the user is interested in
  *	deleteSessionInWishlist(SessionKey) -- removes the session from the user’s list of sessions they are interested in attending

5. Write Python functions filling out a template of an API (tournament.py)  
6. Run a test suite to verify your code (tournament_test.py)  
7. 


## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
