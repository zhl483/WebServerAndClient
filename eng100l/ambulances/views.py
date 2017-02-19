# Create your views here.

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse, reverse_lazy
from django.shortcuts import render_to_response
from django.template import RequestContext

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from braces import views
from django.views import View

from django.http import HttpResponse
from django.http import JsonResponse
from django.template import loader
from django.views.decorators.csrf import csrf_exempt
import json
import ast

from django.contrib.gis.geos import Point

from .models import Ambulances, Reporter
from .forms import AmbulanceUpdateForm, AmbulanceCreateForm, ReporterCreateForm


class AmbulanceCreateView(CreateView):
    model = Ambulances
    context_object_name = "ambulance_form"
    form_class = AmbulanceCreateForm
    success_url = reverse_lazy('ambulance_create')


class AmbulanceInfoView(views.JSONResponseMixin, View):

    def build_json(self, pk):
        record = Ambulances.objects.get(pk=pk)
        json = {
            "status": record.status,
            "reporter": record.reporter if record.reporter else "No Reporter",
            "location": "(" + repr(record.location.x) + ","
            + repr(record.location.y) + ")"
        }
        return json

    def get_ajax(self, request, pk):
        json = self.build_json(pk)
        return self.render_json_response(json)

    def get(self, request, pk):
        json = self.build_json(pk)
        return self.render_json_response(json)


class AmbulanceUpdateView(views.JSONResponseMixin, View):

    def update_ambulance(self, pk):
        record = Ambulances.objects.get(pk=pk)

        # lookup status
        status = self.request.GET.get('status')
        if status:
            # update record
            record.status = status

        # lookup location
        longitude = float(self.request.GET.get('long'))
        latitude = float(self.request.GET.get('lat'))
        if longitude and latitude:
            # update record
            location = Point(longitude, latitude, srid=4326)
            record.location = location

        # save updated record
        record.save()
        return record

    def get_ajax(self, request, pk):
        record = self.update_ambulance(pk)
        # return HttpResponse('Got it!')

        json = {"status": record.status,
                "long": record.location.x,
                "lat": record.location.y
                }
        return self.render_json_response(json)

    # Through the browser, can render HTML for human-friendly viewing
    def get(self, request, pk):
        record = self.update_ambulance(pk)
        return HttpResponse('Got it!')


class ReporterCreateView(CreateView):
    model = Reporter
    context_object_name = "reporter_form"
    form_class = ReporterCreateForm
    success_url = reverse_lazy('list')


class AmbulanceView(views.JSONResponseMixin, views.AjaxResponseMixin, ListView):
    model = Ambulances
    context_object_name = 'ambulances_list'

    def get_ajax(self, request, *args, **kwargs):
        json = []
        entries = self.get_queryset()
        for entry in entries:
            json.append({
                'type': 'Ambulances',
                'location': {'x': entry.location.x,
                             'y': entry.location.y},
                'license_plate': entry.license_plate,
                'status': entry.status,
            })
        return self.render_json_response(json)

    def index(request):
        ambulances = Ambulances.objects.all()
        len(ambulances)
        return render(request, 'ambulances/ambulances_list.html', {'ambulances_list': ambulances})

    def lat(self):
        return float(self.request.GET.get('lat') or 32.52174913333495)

    def lng(self):
        return float(self.request.GET.get('lng') or -117.0096155300208)


class AllAmbulancesView(views.JSONResponseMixin, View):

    def build_json(self):

        ambulances = Ambulances.objects.all()
        json = []

        for ambulance in ambulances:
            json.append({
                "id": ambulance.license_plate,
                "status": ambulance.status,
                "reporter": ambulance.reporter if ambulance.reporter else "No Reporter",
                "location": "(" + repr(ambulance.location.x) + ","
                            + repr(ambulance.location.y) + ")"
            })
        return json

    def get_ajax(self, request):
        json = self.build_json()
        return self.render_json_response(json)

    def get(self, request):
        json = self.build_json()
        return self.render_json_response(json)

class CreateRoute(views.JSONResponseMixin, View):
    def post(self, request):
        # json_data = json.loads(request.body)
        points = ast.literal_eval(request.body)
        text = ""
        for p in points:
            text = text + p["alex"] + "\n"
        return HttpResponse(text)

class AmbulanceMap(views.JSONResponseMixin, views.AjaxResponseMixin, ListView):
    def get(self, request):
        return render(request, 'ambulances/ambulance_map.html')