from enum import Enum
from django.utils import timezone

from django.db import models

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point

from django.contrib.auth.models import User

# lazy client property
client = None
def get_client():

    global client
    
    if not client:
        from ambulances.mqtt import publish as mqtt
        client = mqtt.get_client()
    return client

# Hospital model

class Hospital(models.Model):
    
    name = models.CharField(max_length=254, unique=True)
    address = models.CharField(max_length=254, default="")
    location = models.PointField(srid=4326, null=True, blank=True)
    
    # comment
    comment = models.CharField(max_length=254, default="")
    
    updated_by = models.ForeignKey(User,
                                   on_delete=models.CASCADE)
    updated_on = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs) 
        get_client().publish_hospital(self)

    def delete(self, *args, **kwargs):
        get_client().remove_hospital(self)
        super().delete(*args, **kwargs)
        
    def __str__(self):
        return ('> Hospital {}(id={})\n' +
                '   Address: {}\n' +
                '  Location: {}\n' +
                '   Updated: {} by {}').format(self.name,
                                               self.id,
                                               self.address,
                                               self.location,
                                               self.updated_by,
                                               self.updated_on)

class EquipmentType(Enum):
    B = 'Boolean'
    I = 'Integer'
    S = 'String'
    
class Equipment(models.Model):

    name = models.CharField(max_length=254, unique=True)

    EQUIPMENT_ETYPE_CHOICES = \
        [(m.name, m.value) for m in EquipmentType]
    etype = models.CharField(max_length=1,
                             choices = EQUIPMENT_ETYPE_CHOICES)
    
    toggleable = models.BooleanField(default=False)

    def __str__(self):
        return "{}: {} ({})".format(self.id, self.name, self.toggleable)


class HospitalEquipment(models.Model):

    hospital = models.ForeignKey(Hospital,
                                 on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment,
                                  on_delete=models.CASCADE)

    value = models.CharField(max_length=254)
    comment = models.CharField(max_length=254)
    
    quantity = models.IntegerField(default=0)
    
    updated_by = models.ForeignKey(User,
                                   on_delete=models.CASCADE)
    updated_on = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        created = self.pk is None
        super().save(*args, **kwargs) 
        client = get_client()
        client.publish_hospital_equipment(self)
        if created:
            client.publish_hospital_metadata(self.hospital)

    def delete(self, *args, **kwargs):
        client = get_client()
        client.remove_hospital_equipment(self)
        client.publish_hospital_metadata(self.hospital)
        super().delete(*args, **kwargs)
        
    class Meta:
        unique_together = ('hospital', 'equipment',)

    def __str__(self):
        return "Hospital: {}, Equipment: {}, Count: {}".format(self.hospital, self.equipment, self.quantity)
