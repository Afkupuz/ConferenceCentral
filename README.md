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
5. Additional queries and solve a query problem:
  * Let’s say that you don't like workshops and you don't like sessions after 7 pm. How would you handle a query for all non-workshop sessions before 7 pm? What is the problem for implementing this query? What ways to solve it did you think of?
6. Add a featured speaker task:
  * When a new session is added to a conference, check the speaker. If there is more than one session by this speaker at this conference, also add a new Memcache entry that features the speaker and session names. You can choose the Memcache key.
The logic above should be handled using App Engine's Task Queue.

##Grading:  
Grading was based on functionality, table design, code quality and documentation  
  
Extra Credit:
Create entity for speakers
Implement solution to query

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
2. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
3. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
4. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
5. Run the app with the dev-server using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
6. (Optional) Generate your client library(ies) with [the endpoints tool][6].
7. Deploy your application.

## My Project
### Sessions
Sessions are children of their parent conference so that they are related when searched. Each session is able to take multiple speakers and relevant information such as dates and times. Time should be entered in 24 hour time and the date is required to be in the year-date-day format. This is important when using the APIs explorer but can be regulated on the front end (not implemented yet). Speakers were made into entities so that they can be tracked and registered and rated as individual objects as opposed to having them be entered variables in the session object.  
I have implemented an entity for speakers using the _createSpeaker, _copySpeakerToForm, createSpeaker, and getSpeaker methods and endpoints.  
### WishList
Wishlists are added as a parameter to a user profile and stored in a list as a web-safe key. This makes it easy to retrieve, add to, and remove from a users profile.
### Additional Queries
getSpeakerByRating()  
My first query was to get speakers by rating. This was easy to implement since the speakers are entities with a rating parameter. The operator requires the use of text based symbols:  
            'EQ'   :   '='  
            'GT'   :   '>'  
            'GTEQ' :   '>='  
            'LT'   :   '<'  
            'LTEQ' :   '<='  
            'NE'   :   '!=' 
  
getPercentFullConf()  
The second query I implemented was more complicated. I decided that finding popular conferences would be made easier if people could see which were the most full. This was best expressed as a percentage, so I imported some math functions and used python to help with the fact that I needed multiple operators. Ultimately python does the heavy lifting of collecting conferences and calculating their percent full status, comparing to users parameters, and sorting the results. Users should use text based symbols for the operator as above.  
  
getDoubleQuerySession()  
The query question posed is a similar issue to my percentage based query in that it requires two inequalities:  
"Let’s say that you don't like workshops and you don't like sessions after 7 pm. How would you handle a query for all non-workshop sessions before 7 pm? What is the problem for implementing this query? What ways to solve it did you think of?"  
You are basically looking for any session who's time starts before 7pm or time > 1900  
AND  
Is not a workshop. The fact that this is an inequality is not immediately obvious. The way this is requested is: type > workshop < type  
To solve this, I let python to do a lot of the heavy lifting. I started by requesting all sessions that start before the given time. This gives a smaller pool to work with. Once collected, I used a python for loop to check each session's type. If the session type did not match the given parameter, it was added to a secondary list. Once complete, the list was returned as the results of the filter.  
### Featured Speaker Task
Adding the featured speaker gave me some trouble, but ultimately when a session is created, it passes the parent conference key and its own key to the task manager which passes the information to a method that picks it apart and finds multiple speakers. If there are multiple speakers, they are added to the memcache along with associated sessions.

[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
