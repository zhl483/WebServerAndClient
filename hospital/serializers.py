import django.db.models as models
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from rest_framework import serializers
from drf_extra_fields.geo_fields import PointField

from .models import Hospital, Equipment, HospitalEquipment

# Hospital serializers
class HospitalSerializer(serializers.ModelSerializer):

    location = PointField(required=False)
    
    class Meta:
        model = Hospital
        fields = [ 'id',
                   'number', 'street', 'unit', 'neighborhood',
                   'city', 'state', 'zipcode', 'country',
                   'location',
                   'name',
                   'comment', 'updated_by', 'updated_on' ]
        read_only_fields = ('updated_by',)
        
    def create(self, validated_data):

        # get current user
        user = validated_data['updated_by']

        # check credentials
        # only super can create
        if not user.is_superuser:
            raise PermissionDenied()
    
        return super().create(validated_data)
    
    def update(self, instance, validated_data):

        # get current user
        user = validated_data['updated_by']

        # check credentials
        if not user.is_superuser:
            
            # serializer.instance will always exist!
            if not user.profile.hospitals.filter(can_write=True,
                                                 hospital=instance.id):
                raise PermissionDenied()

        return super().update(instance, validated_data)
    
# HospitalEquipment serializers
class HospitalEquipmentSerializer(serializers.ModelSerializer):

    hospital_name = serializers.CharField(source='hospital.name')
    equipment_name = serializers.CharField(source='equipment.name')
    equipment_etype = serializers.CharField(source='equipment.etype')
    
    class Meta:
        model = HospitalEquipment
        fields = ('hospital_id', 'hospital_name',
                  'equipment_id', 'equipment_name', 'equipment_etype',
                  'value', 'comment',
                  'updated_by', 'updated_on')
        read_only_fields = ('hospital_id', 'hospital_name',
                            'equipment_id', 'equipment_name', 'equipment_etype',
                            'updated_by',)

    def validate(self, data):

        # call super
        validated_data = super().validate(data)

        # TODO: validate equipment value using equipment_etype
        return validated_data
        
# EquipmentMetadata serializer
class EquipmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Equipment
        fields = '__all__'
