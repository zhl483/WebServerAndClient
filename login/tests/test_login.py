import logging
import time
from django.test import TestCase
from django.test import Client

from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.auth.hashers import get_hasher, check_password

from rest_framework.parsers import JSONParser
from io import BytesIO

from ambulance.models import Ambulance, \
    AmbulanceStatus, AmbulanceCapability

from hospital.models import Hospital, \
    Equipment, HospitalEquipment, EquipmentType

from ..models import Profile, AmbulancePermission, HospitalPermission, \
    TemporaryPassword

from ..serializers import ProfileSerializer, ExtendedProfileSerializer

from ..views import LoginView, SignupView, LogoutView, \
    MQTTLoginView, MQTTSuperuserView, MQTTAclView

from mqtt.tests.client import MQTTTestCase, MQTTTestClient
from mqtt.client import MQTTException

logger = logging.getLogger(__name__)

class MyTestCase(MQTTTestCase):

    @classmethod
    def setUpClass(cls):

        # create server
        super().setUpClass()

        # instantiate client
        cls.client = Client()

            
class TestProfile(MyTestCase):

    def test_profile_serializer(self):

        # test ProfileSerializer
        for u in (self.u1, self.u2, self.u3):
            serializer = ProfileSerializer(u.profile)
            result = {
                'ambulances': [
                    {
                        'ambulance_id': e.ambulance.pk,
                        'ambulance_identifier': e.ambulance.identifier,
                        'can_read': e.can_read,
                        'can_write': e.can_write
                    }
                    for e in u.profile.ambulances.all()
                ],
                'hospitals': [
                    {
                        'hospital_id': e.hospital.pk,
                        'hospital_name': e.hospital.name,
                        'can_read': e.can_read,
                        'can_write': e.can_write
                    }
                    for e in u.profile.hospitals.all()
                ]
            }
            self.assertDictEqual(serializer.data, result)

    def test_extended_profile_serializer(self):

        self.maxDiff = None
        
        # test ProfileSerializer

        # regular users is just like ProfileSerializer
        for u in (self.u2, self.u3):
            serializer = ExtendedProfileSerializer(u.profile)
            result = {
                'ambulances': [
                    {
                        'ambulance_id': e.ambulance.pk,
                        'ambulance_identifier': e.ambulance.identifier,
                        'can_read': e.can_read,
                        'can_write': e.can_write
                    }
                    for e in u.profile.ambulances.all()
                ],
                'hospitals': [
                    {
                        'hospital_id': e.hospital.pk,
                        'hospital_name': e.hospital.name,
                        'can_read': e.can_read,
                        'can_write': e.can_write
                    }
                    for e in u.profile.hospitals.all()
                ]
            }
            self.assertDictEqual(serializer.data, result)

        # super will see all ambulances and hospitals
        u = self.u1
        serializer = ExtendedProfileSerializer(u.profile)
        result = {
            'ambulances': [
                {
                    'ambulance_id': e.pk,
                    'ambulance_identifier': e.identifier,
                    'can_read': True,
                    'can_write': True
                }
                for e in Ambulance.objects.all()
            ],
            'hospitals': [
                {
                    'hospital_id': e.pk,
                    'hospital_name': e.name,
                    'can_read': True,
                    'can_write': True
                }
                for e in Hospital.objects.all()
            ]
        }
        self.assertDictEqual(serializer.data, result)
            
class TestProfileViewset(MyTestCase):

    def test_profile_viewset(self):

        # instantiate client
        client = Client()

        # login as admin
        client.login(username=settings.MQTT['USERNAME'], password=settings.MQTT['PASSWORD'])

        # retrieve own
        response = client.get('/api/user/{}/profile/'.format(str(self.u1.username)),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        result = JSONParser().parse(BytesIO(response.content))
        answer = ExtendedProfileSerializer(self.u1.profile).data
        self.assertDictEqual(result, answer)
        
        # retrieve someone else's
        response = client.get('/api/user/{}/profile/'.format(str(self.u2.username)),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        result = JSONParser().parse(BytesIO(response.content))
        answer = ExtendedProfileSerializer(self.u2.profile).data
        self.assertDictEqual(result, answer)

        # retrieve someone else's
        response = client.get('/api/user/{}/profile/'.format(str(self.u3.username)),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        result = JSONParser().parse(BytesIO(response.content))
        answer = ExtendedProfileSerializer(self.u3.profile).data
        self.assertDictEqual(result, answer)
        
        # logout
        client.logout()

        # login as testuser1
        client.login(username='testuser1', password='top_secret')
        
        # retrieve own
        response = client.get('/api/user/{}/profile/'.format(str(self.u2.username)),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        result = JSONParser().parse(BytesIO(response.content))
        answer = ExtendedProfileSerializer(self.u2.profile).data
        self.assertDictEqual(result, answer)
        
        # retrieve someone else's
        response = client.get('/api/user/{}/profile/'.format(str(self.u1.username)),
                              follow=True)
        self.assertEqual(response.status_code, 403)
        
        response = client.get('/api/user/{}/profile/'.format(str(self.u3.username)),
                              follow=True)
        self.assertEqual(response.status_code, 403)
        
        # logout
        client.logout()
        
class TestLogin(MyTestCase):
            
    def test_login(self):

        # blank login
        response = self.client.get('/auth/login/')
        self.assertEqual(response.status_code, 200)

        # incorrect username
        response = self.client.post('/auth/login/', { 'username': 'testuser11',
                                                  'password': 'top_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, False)
        
        # incorrect password
        response = self.client.post('/auth/login/', { 'username': 'testuser1',
                                                  'password': 'top_secret0' },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, False)
        
        # correct login
        response = self.client.post('/auth/login/', { 'username': 'testuser1',
                                                  'password': 'top_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, True)
        self.assertEqual(response.context['user'].username, 'testuser1')
        self.assertEqual(response.context['user'].is_superuser, False)

        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, False)

        # login user2
        response = self.client.post('/auth/login/', { 'username': 'testuser2',
                                                  'password': 'very_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, True)
        self.assertEqual(response.context['user'].username, 'testuser2')
        self.assertEqual(response.context['user'].is_superuser, False)

        # login admin
        response = self.client.post('/auth/login/', { 'username': settings.MQTT['USERNAME'],
                                                  'password': settings.MQTT['PASSWORD'] },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, True)
        self.assertEqual(response.context['user'].username, settings.MQTT['USERNAME'])
        self.assertEqual(response.context['user'].is_superuser, True)

        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].is_authenticated, False)
        
class TestMQTTLogin(MyTestCase):

    def test_mqtt_login(self):

        # blank login
        response = self.client.get('/auth/mqtt/login/')
        self.assertEqual(response.status_code, 200)

        # incorrect username
        response = self.client.post('/auth/mqtt/login/',
                               { 'username': 'testuser11',
                                 'password': 'top_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # incorrect username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': 'testuser11' },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # incorrect password
        response = self.client.post('/auth/mqtt/login/',
                               { 'username': 'testuser1',
                                 'password': 'top_secret0' },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # incorrect username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': 'testuser1' },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # correct login
        response = self.client.post('/auth/mqtt/login/',
                               { 'username': 'testuser1',
                                 'password': 'top_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # incorrect username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': 'testuser1' },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)

        # login user2
        response = self.client.post('/auth/mqtt/login/',
                               { 'username': 'testuser2',
                                 'password': 'very_secret' },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # incorrect username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': 'testuser2' },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': settings.MQTT['USERNAME'] },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        
        # login admin
        response = self.client.post('/auth/mqtt/login/',
                               { 'username': settings.MQTT['USERNAME'],
                                 'password': settings.MQTT['PASSWORD'] },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # username superuser
        response = self.client.post('/auth/mqtt/superuser/',
                               { 'username': settings.MQTT['USERNAME'] },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        
        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)

class TestMQTTACLSubscribe(MyTestCase):

    def test_mqtt_acl_subscribe(self):

        # Settings
        
        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/settings' },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Profile
        
        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/user/testuser1/profile' },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/profile' },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # Hospitals
        
        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/data'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/data'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/data'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/equipment/rx/data'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/equipment/beds/data'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/equipment/rx/data'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/hospital/{}/metadata'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # Ambulances

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can't subscribe
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '1',
                                 'topic': '/ambulance/{}/data'.format(self.a2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

class TestMQTTACLPublish(MyTestCase):

    def test_mqtt_acl_publish(self):

        # Ambulance data
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/ambulance/{}/data'.format(self.a1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/ambulance/{}/data'.format(self.a2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/ambulance/{}/data'.format(self.a3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/ambulance/{}/data'.format(self.a1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/ambulance/{}/data'.format(self.a2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/ambulance/{}/data'.format(self.a3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # Hospital data
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/hospital/{}/data'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/hospital/{}/data'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser1',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser1/hospital/{}/data'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/hospital/{}/data'.format(self.h1.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # can't publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/hospital/{}/data'.format(self.h2.id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # can publish
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': 'testuser2',
                                 'clientid': 'test_client',
                                 'acc': '2',
                                 'topic': '/user/testuser2/hospital/{}/data'.format(self.h3.id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)

        # Client data

        username = 'testuser2'
        client_id = 'test_client'
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': username,
                                 'clientid': client_id,
                                 'acc': '2',
                                 'topic': '/user/{}/client/{}/status'.format(username, client_id) },
                               follow=True)
        self.assertEqual(response.status_code, 200)

        # invalid username
        
        username = 'testuser2'
        client_id = 'test_client'
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': username,
                                 'clientid': client_id,
                                 'acc': '2',
                                 'topic': '/user/{}/client/{}/status'.format(username + 'o', client_id) },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
        # invalid client_id
        
        username = 'testuser2'
        client_id = 'test_client'
        response = self.client.post('/auth/mqtt/acl/',
                               { 'username': username,
                                 'clientid': client_id,
                                 'acc': '2',
                                 'topic': '/user/{}/client/{}/status'.format(username, client_id + 'o') },
                               follow=True)
        self.assertEqual(response.status_code, 403)
        
class TestMQTTConnect(MyTestCase):

    def is_connected(self, client, MAX_TRIES = 10):

        # connected?
        k = 0
        while not client.connected and k < MAX_TRIES:
            k += 1
            client.loop()

        self.assertEqual(client.connected, True)
        
    def test_connect(self):

        # Start client as admin
        broker = {
            'HOST': 'localhost',
            'PORT': 1883,
            'KEEPALIVE': 60,
            'CLEAN_SESSION': True
        }
        broker.update(settings.MQTT)
        broker['CLIENT_ID'] = 'test_mqtt_connect_admin'
        
        self.is_connected(MQTTTestClient(broker))
        
        # Start client as common user
        broker['USERNAME'] = 'testuser1'
        broker['PASSWORD'] = 'top_secret'
        
        self.is_connected(MQTTTestClient(broker))

        # Start client as common user
        broker['USERNAME'] = 'testuser2'
        broker['PASSWORD'] = 'very_secret'

        self.is_connected(MQTTTestClient(broker))
        
        # wrong username
        broker['USERNAME'] = 'testuser22'
        broker['PASSWORD'] = 'very_secret'

        with self.assertRaises(MQTTException):
        
            self.is_connected(MQTTTestClient(broker))
            
        # wrong password
        broker['USERNAME'] = 'testuser2'
        broker['PASSWORD'] = 'very_secreto'

        with self.assertRaises(MQTTException):

            self.is_connected(MQTTTestClient(broker))

class TestMQTTSubscribe(MyTestCase):

    def is_connected(self, client, MAX_TRIES = 10):

        # connected?
        k = 0
        while not client.connected and k < MAX_TRIES:
            k += 1
            client.loop()

        self.assertEqual(client.connected, True)
        
    def is_subscribed(self, client, MAX_TRIES = 10):

        client.loop_start()
        
        # connected?
        k = 0
        while len(client.subscribed) and k < MAX_TRIES:
            k += 1
            time.sleep(1)
            
        client.loop_stop()
        
        self.assertEqual(len(client.subscribed), 0)
    
    def test_subscribe(self):

        # Start client as admin
        broker = {
            'HOST': 'localhost',
            'PORT': 1883,
            'KEEPALIVE': 60,
            'CLEAN_SESSION': True
        }
        broker.update(settings.MQTT)
        broker['CLIENT_ID'] = 'test_mqtt_subscribe_admin'
        
        client = MQTTTestClient(broker,
                                check_payload = False)

        self.is_connected(client)
        
        # subscribe to topics
        client.expect('user/{}/error'.format(broker['USERNAME']))
        client.expect('settings')
        client.expect('user/{}/profile'.format(broker['USERNAME']))
        
        client.expect('ambulance/{}/data'.format(self.a1.id))
        client.expect('ambulance/{}/data'.format(self.a2.id))
        client.expect('ambulance/{}/data'.format(self.a3.id))

        client.expect('hospital/{}/data'.format(self.h1.id))
        client.expect('hospital/{}/data'.format(self.h2.id))
        client.expect('hospital/{}/data'.format(self.h3.id))
            
        client.expect('hospital/{}/equipment/+/data'.format(self.h1.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h2.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h3.id))

        self.is_subscribed(client)

        client.wait()
        
        # Start client as common user
        broker['USERNAME'] = 'testuser1'
        broker['PASSWORD'] = 'top_secret'

        client = MQTTTestClient(broker,
                                check_payload = False)

        self.is_connected(client)
        
        # subscribe to topics
        client.expect('user/{}/error'.format(broker['USERNAME']))
        client.expect('settings')
        client.expect('user/{}/profile'.format(broker['USERNAME']))
        
        client.expect('ambulance/{}/data'.format(self.a1.id))
        client.expect('ambulance/{}/data'.format(self.a2.id))
        client.expect('ambulance/{}/data'.format(self.a3.id))

        client.expect('hospital/{}/data'.format(self.h1.id))
        client.expect('hospital/{}/data'.format(self.h2.id))
        client.expect('hospital/{}/data'.format(self.h3.id))
            
        client.expect('hospital/{}/equipment/+/data'.format(self.h1.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h2.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h3.id))

        # client doesn't know it cannot subscribe to certain topics!
        # full testing in test_mqtt
        self.is_subscribed(client)

        client.wait()
        
        # Start client as common user
        broker['USERNAME'] = 'testuser2'
        broker['PASSWORD'] = 'very_secret'

        client = MQTTTestClient(broker,
                                check_payload = False)

        self.is_connected(client)
        
        # subscribe to topics
        client.expect('user/{}/error'.format(broker['USERNAME']))
        client.expect('settings')
        client.expect('user/{}/profile'.format(broker['USERNAME']))
        
        client.expect('ambulance/{}/data'.format(self.a1.id))
        client.expect('ambulance/{}/data'.format(self.a2.id))
        client.expect('ambulance/{}/data'.format(self.a3.id))

        client.expect('hospital/{}/data'.format(self.h1.id))
        client.expect('hospital/{}/data'.format(self.h2.id))
        client.expect('hospital/{}/data'.format(self.h3.id))
            
        client.expect('hospital/{}/equipment/+/data'.format(self.h1.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h2.id))
        client.expect('hospital/{}/equipment/+/data'.format(self.h3.id))

        # client doesn't know it cannot subscribe to certain topics!
        # full testing in test_mqtt
        self.is_subscribed(client)
        
        client.wait()

class TestMQTTLoginTempPassword(MyTestCase):

    def test(self):

        # instantiate client
        client = Client()

        # retrieve password hash without being logged in
        username = 'admin'
        response = client.get('/api/user/{}/password/'.format(username),
                              follow=True)
        result = JSONParser().parse(BytesIO(response.content))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(result,
                         { 'detail': 'Authentication credentials were not provided.'})
        
        # login as admin
        username = settings.MQTT['USERNAME']
        client.login(username=settings.MQTT['USERNAME'],
                     password=settings.MQTT['PASSWORD'])

        # retrieve password hash
        response = client.get('/api/user/{}/password/'.format(username),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        encoded = JSONParser().parse(BytesIO(response.content))

        # retrieve temporary password
        password = TemporaryPassword.objects.get(user__username = username).password
        
        self.assertEqual(check_password(password, encoded), True)

        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        
        # mqtt login with correct temporary password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': 'admin',
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        
        # mqtt login with incorrect username
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': 'admino',
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 403)

        # mqtt login with incorrect encoded password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': 'admin',
                                      'password': encoded + 'r' },
                                    follow=True)
        self.assertEqual(response.status_code, 403)

        
        
        # login as testuser1
        username = 'testuser1'
        client.login(username=username, password='top_secret')

        # retrieve password hash
        response = client.get('/api/user/{}/password/'.format(username),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        encoded = JSONParser().parse(BytesIO(response.content))

        # retrieve temporary password
        password = TemporaryPassword.objects.get(user__username = username).password
        
        self.assertEqual(check_password(password, encoded), True)

        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        
        # mqtt login with correct temporary password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username,
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        
        # mqtt login with incorrect username
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username + 'o',
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 403)

        # mqtt login with incorrect encoded password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username,
                                      'password': encoded + 'r' },
                                    follow=True)
        self.assertEqual(response.status_code, 403)



        # login as testuser2
        username = 'testuser2'
        client.login(username=username, password='very_secret')

        # retrieve password hash
        response = client.get('/api/user/{}/password/'.format(username),
                              follow=True)
        self.assertEqual(response.status_code, 200)
        encoded = JSONParser().parse(BytesIO(response.content))

        # retrieve temporary password
        password = TemporaryPassword.objects.get(user__username = username).password
        
        self.assertEqual(check_password(password, encoded), True)

        # logout
        response = self.client.get('/auth/logout/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        
        # mqtt login with correct temporary password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username,
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        
        # mqtt login with incorrect username
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username + 'o',
                                      'password': encoded },
                                    follow=True)
        self.assertEqual(response.status_code, 403)

        # mqtt login with incorrect encoded password
        response = self.client.post('/auth/mqtt/login/',
                                    { 'username': username,
                                      'password': encoded + 'r' },
                                    follow=True)
        self.assertEqual(response.status_code, 403)

        
