from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response

from .models import Vote
from base import mods

def choices_store(request):
  """ 
    * voting: id
    * voter: id
    * votes: list<{ "a": int, "b": int }>
    * voting_type: "choices"
  """
  vid = request.data.get('voting')
  voting = mods.get('voting', params={'id': vid})
  if not voting or not isinstance(voting, list):
      return Response({}, status=status.HTTP_401_UNAUTHORIZED)
  start_date = voting[0].get('start_date', None)
  # print ("Start date: "+  start_date)
  end_date = voting[0].get('end_date', None)
  #print ("End date: ", end_date)
  not_started = not start_date or timezone.now() < parse_datetime(start_date)
  #print (not_started)
  is_closed = end_date and parse_datetime(end_date) < timezone.now()
  if not_started or is_closed:
      return Response({}, status=status.HTTP_401_UNAUTHORIZED)

  uid = request.data.get('voter')
  votes = request.data.get('votes')

  if not vid or not uid or not votes:
      return Response({}, status=status.HTTP_400_BAD_REQUEST)

  # validating voter
  if request.auth:
      token = request.auth.key
  else:
      token = "NO-AUTH-VOTE"
  voter = mods.post('authentication', entry_point='/getuser/', json={'token': token})
  voter_id = voter.get('id', None)
  if not voter_id or voter_id != uid:
      # print("por aqui 59")
      return Response({}, status=status.HTTP_401_UNAUTHORIZED)

  # the user is in the census
  perms = mods.get('census/{}'.format(vid), params={'voter_id': uid}, response=True)
  if perms.status_code == 401:
      # print("por aqui 65")
      return Response({}, status=status.HTTP_401_UNAUTHORIZED)
        
  for v in votes:
    a = v.get("a")
    b = v.get("b")

    defs = { "a": a, "b": b }
    v, _ = Vote.objects.get_or_create(voting_id=vid, voter_id=uid,
                                      defaults=defs)
    v.a = a
    v.b = b

    v.save()