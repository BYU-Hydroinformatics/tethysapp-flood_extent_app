from django.http import Http404, HttpResponse, JsonResponse
import xarray
import numpy as np
import pandas as pd
import os
import os.path
import requests
import json
import ast
from .app import FloodExtentApp as app
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String
import logging


Base = declarative_base()


class Regiondb(Base):

    __tablename__ = 'regions'

    region = Column(String, primary_key=True)
    filename = Column(String)
    watershed = Column(String)
    subbasin = Column(String)
    host = Column(String)
    spt_river = Column(Integer)


def createnetcdf(request):

    token = app.get_custom_setting('spt_access_token')
    api_url = app.get_custom_setting('spt_url') + '/api/GetForecast/'
    thredds = app.get_custom_setting('thredds_folder')

    region = request.GET.get('region')

    Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
    session = Session()

    dbs = session.query(Regiondb).all()

    for db in dbs:
        if db.region == region:
            filename = db.filename
            watershed = db.watershed
            subbasin = db.subbasin

    session.close()

    catchfile = filename + 'catchproj.nc'
    handfile = filename + 'handproj.nc'
    ratfile = filename + 'ratingcurve.csv'

    gridid = int(request.GET.get('gridid'))
    date = request.GET.get('date')
    forecasttype = request.GET.get('forecasttype')

    catchfloodnetcdf = thredds + catchfile
    handnetcdf = thredds + handfile
    ratingcurve = thredds + ratfile

    catchfloods = xarray.open_dataset(catchfloodnetcdf, autoclose=True).catchproj
    hand = xarray.open_dataset(handnetcdf, autoclose=True).handproj

    # scaling down grid netcdf to specific gridid
    catlat = catchfloods.where(catchfloods.values == gridid).dropna('lat', how='all')
    gridonly = catlat.where(catlat.values == gridid).dropna('lon', how='all')

    lats = gridonly.lat.values
    lons = gridonly.lon.values

    # scaling down hand netcdf to specific gridid size
    handsmall = hand.sel(lat=lats, method='nearest')
    handsmall = handsmall.sel(lon=lons, method='nearest')

    ratcurve = pd.read_csv(ratingcurve)
    gridcurve = ratcurve[ratcurve.GridID == gridid]
    comid = int(gridcurve.loc[gridcurve['H'] == 1, 'COMID'].iloc[0])
    gridcurve = ratcurve[ratcurve.GridID == gridid]
    minQ = float(gridcurve.loc[gridcurve['H'] == 1, 'Q'].iloc[0])
    maxQ = float(gridcurve['Q'].iloc[-1])
    maxH = float(gridcurve['H'].iloc[-1])

    request_params = dict(watershed_name=watershed, subbasin_name=subbasin, reach_id=comid,
                          forecast_folder=date, stat_type=forecasttype, return_format='csv')
    request_headers = dict(Authorization="Token " + token)
    res = requests.get(api_url, params=request_params,
                       headers=request_headers)

    if res:

        return_obj = {'success': True}

        content = res.content.splitlines()

        times = []
        flowlist = []

        for timesteps in content:
            ts = timesteps.split(",")
            times.append(ts[0][:19])
            flowlist.append(ts[1])

        del times[0]
        del flowlist[0]

        heights = []

        for b in range(0, len(times)):
            flow = (float(flowlist[b]))
            if flow == 0:
                H = -1.0
            else:
                H = 0.0
            if flow > maxQ:

                return_obj['alertmessage'] = "Streamflow exceeds rating curve. Increase rating curve above " + str(
                    maxH) + " meters"

                heights.append(maxH)

            elif flow > minQ:
                H = float(gridcurve.loc[gridcurve['Q'] > flow, 'H'].iloc[0]) - 1
                heights.append(H)
            else:
                heights.append(H)

        maxheight = str(max(heights))

        return_obj['maxheight'] = maxheight

        flooded = handsmall.to_dataset()

        index = 0
        height = heights[index]
        flooded_areas = gridonly.copy()
        flooded['timeseries'] = flooded_areas
        flooded.timeseries.values = gridonly.where(gridonly != gridid, height).values
        flooded.timeseries.values = xarray.where(flooded.timeseries >= flooded.handproj, flooded.handproj,
                                                 np.nan).values
        floodedarray = flooded.timeseries.expand_dims('time', axis=2).to_masked_array()
        oldheight = ''

        for index in range(1, len(heights)):
            if heights[index] == oldheight:
                floodlen = len(floodedarray[0][0])
                floodedarray = np.insert(floodedarray, floodlen, floodedvalues, axis=2)
            else:
                height = heights[index]
                floodlen = len(floodedarray[0][0])
                flooded_areas = gridonly.copy()
                flooded['step'] = flooded_areas
                flooded.step.values = gridonly.where(gridonly != gridid, height).values
                floodedvalues = xarray.where(flooded.step >= flooded.handproj, flooded.handproj, np.nan).values
                floodedarray = np.insert(floodedarray, floodlen, floodedvalues, axis=2)
                flooded.__delitem__('step')
                oldheight = height

        times = pd.to_datetime(times)
        ds = xarray.Dataset({'Height': (['lat', 'lon', 'time'], floodedarray)},
                            coords={'lon': lons,
                                    'lat': lats,
                                    'time': times})

        ds.to_netcdf(thredds + "floodedgrid" + str(gridid) + ".nc")

        return_obj['gridid'] = gridid

        return JsonResponse(return_obj)

    else:

        return_obj = {'success': True,
                      'errormessage': "Error retrieving flows from the Streamflow Prediction Tool: " + res.content}

        return JsonResponse(return_obj)


def displaydrainagelines(request):
    return_obj = {
        'success': False
    }

    # Check if its an ajax post request
    if request.is_ajax() and request.method == 'GET':

        return_obj['success'] = True
        geolayer = request.GET.get('geolayer')
        thredds = app.get_custom_setting('thredds_folder')
        geofile = thredds + geolayer

        if os.path.isfile(geofile):
            with open(geofile, 'r') as f:
                fullstream = ''
                streams = f.readlines()
                for i in range(0, len(streams)):
                    fullstream += streams[i]
            return_obj = json.loads(fullstream)

            return JsonResponse(return_obj)
        else:
            return_obj['errormessage'] = 'No ' + geolayer + ' exists on the Thredds server. Please upload correct file'
            return JsonResponse(return_obj)


def displaywarningpts(request):
    return_obj = {
        'success': False
    }

    # Check if its an ajax post request
    if request.is_ajax() and request.method == 'GET':

        token = app.get_custom_setting('spt_access_token')
        api_url = app.get_custom_setting('spt_url') + '/api/GetWarningPoints/'

        date = request.GET.get('date')
        region = request.GET.get('region')
        nelat = float(request.GET.get('nelat'))
        nelon = float(request.GET.get('nelon'))
        swlon = float(request.GET.get('swlon'))
        swlat = float(request.GET.get('swlat'))

        Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
        session = Session()

        dbs = session.query(Regiondb).all()

        for db in dbs:
            if db.region == region:
                watershed = db.watershed
                subbasin = db.subbasin

        session.close()

        returnperiods = {'2': 'yellow', '10': 'red', '20': 'purple'}

        return_obj = {}
        request_headers = dict(Authorization="Token " + token)
        for periods in returnperiods:

            request_params = dict(watershed_name=watershed, subbasin_name=subbasin,
                                  return_period=int(periods), forecast_folder=date)

            res = requests.get(api_url, params=request_params, headers=request_headers)

            if res:

                points = json.loads(res.content)

                return_points = []

                for point in points['features']:
                    if float(point['geometry']['coordinates'][0]) < nelon and float(point['geometry']['coordinates'][0]) > swlon:
                        if float(point['geometry']['coordinates'][1]) < nelat and float(point['geometry']['coordinates'][1]) > swlat:
                            point['properties']['color'] = returnperiods[periods]
                            return_points.append(point)

                return_obj[periods] = return_points

            else:

                return_obj = {'success': True,
                              'errormessage': "Error retrieving warning points from the Streamflow Prediction Tool: " + res.content}

                return JsonResponse(return_obj)

    return JsonResponse(return_obj)


def createprobnetcdf(request):

    token = app.get_custom_setting('spt_access_token')
    api_url = app.get_custom_setting('spt_url') + '/api/GetEnsemble/'
    thredds = app.get_custom_setting('thredds_folder')

    gridid = int(request.GET.get('gridid'))
    date = request.GET.get('date')

    region = request.GET.get('region')

    Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
    session = Session()

    dbs = session.query(Regiondb).all()

    for db in dbs:
        if db.region == region:
            filename = db.filename
            watershed = db.watershed
            subbasin = db.subbasin

    session.close()

    catchfile = filename + 'catchproj.nc'
    handfile = filename + 'handproj.nc'
    ratfile = filename + 'ratingcurve.csv'

    catchfloodnetcdf = thredds + catchfile
    handnetcdf = thredds + handfile
    ratingcurve = thredds + ratfile

    ratcurve = pd.read_csv(ratingcurve)
    gridcurve = ratcurve[ratcurve.GridID == gridid]
    comid = int(gridcurve.loc[gridcurve['H'] == 1, 'COMID'].iloc[0])
    gridcurve = ratcurve[ratcurve.GridID == gridid]
    minQ = float(gridcurve.loc[gridcurve['H'] == 1, 'Q'].iloc[0])
    maxQ = float(gridcurve['Q'].iloc[-1])
    maxH = float(gridcurve['H'].iloc[-1])

    request_params = dict(watershed_name=watershed, subbasin_name=subbasin,
                          reach_id=comid, forecast_folder=date, ensemble='1-51')
    request_headers = dict(Authorization="Token " + token)
    res = requests.get(api_url, params=request_params, headers=request_headers)

    if res:

        return_obj = {'success': True}

        flows = res.content.splitlines()

        flowlist = []
        times = []

        for flow in flows:
            flowlist.append(flow.split(","))

        catchfloods = xarray.open_dataset(catchfloodnetcdf, autoclose=True).catchproj
        hand = xarray.open_dataset(handnetcdf, autoclose=True).handproj

        # scaling down grid netcdf to specific gridid
        catlat = catchfloods.where(catchfloods.values == gridid).dropna('lat', how='all')
        gridonly = catlat.where(catlat.values == gridid).dropna('lon', how='all')

        lats = gridonly.lat.values
        lons = gridonly.lon.values

        # scaling down hand netcdf to specific gridid size
        handsmall = hand.sel(lat=lats, method='nearest')
        handsmall = handsmall.sel(lon=lons, method='nearest')

        del flowlist[0]

        for vals in flowlist:
            times.append(vals[0])

        for timestep in range(0, len(flowlist)):

            print(str(timestep + 1) + " out of " + str(len(flowlist)))

            heights = []

            for b in range(1, len(flowlist[timestep])):
                flow = (float(flowlist[timestep][b]))
                if flow == 0:
                    H = -1.0
                else:
                    H = 0.0
                if flow > maxQ:

                    return_obj['alertmessage'] = "Streamflow exceeds rating curve. Increase rating curve above " + str(
                        maxH) + " meters"

                    heights.append(maxH)

                elif flow > minQ:
                    H = float(gridcurve.loc[gridcurve['Q'] > flow, 'H'].iloc[0]) - 1
                    heights.append(H)
                else:
                    heights.append(H)

            flooded = handsmall.to_dataset()

            index = 0
            height = heights[index]
            flooded['timeseries'] = gridonly
            flooded.timeseries.values = gridonly.where(gridonly != gridid, height).values
            flooded.timeseries.values = xarray.where(flooded.timeseries >= flooded.handproj, flooded.handproj,
                                                     np.nan).values
            floodedarray = flooded.timeseries.expand_dims('time', axis=2).to_masked_array()
            oldheight = ''

            for index in range(1, len(heights)):
                if heights[index] == oldheight:
                    floodlen = len(floodedarray[0][0])
                    floodedarray = np.insert(floodedarray, floodlen, floodedvalues, axis=2)
                else:
                    height = heights[index]
                    floodlen = len(floodedarray[0][0])
                    flooded['step'] = gridonly
                    flooded.step.values = gridonly.where(gridonly != gridid, height).values
                    floodedvalues = xarray.where(flooded.step >= flooded.handproj, flooded.handproj, np.nan).values
                    floodedarray = np.insert(floodedarray, floodlen, floodedvalues, axis=2)
                    flooded.__delitem__('step')
                    oldheight = height

            non_nans = (~np.isnan(floodedarray)).sum(2)
            floodedprob = np.where(non_nans == 0, np.nan, non_nans) / 51 * 100

            if timestep == 0:
                totfloodedprob = np.expand_dims(floodedprob, axis=2)
            else:
                floodproblen = len(totfloodedprob[0][0])
                totfloodedprob = np.insert(totfloodedprob, floodproblen, floodedprob, axis=2)

        times = pd.to_datetime(times)

        ds = xarray.Dataset({'Flood Probability': (['lat', 'lon', 'times'], totfloodedprob)},
                            coords={'lon': lons,
                                    'lat': lats,
                                    'times': times})

        ds.to_netcdf(thredds + 'prob' + str(gridid) + '.nc')

        return_obj = {'success': True, 'gridid': gridid, 'maxheight': '100'}

        return JsonResponse(return_obj)

    else:

        return_obj = {'success': True,
                      'errormessage': "Error retrieving flows from the Streamflow Prediction Tool: " + res.content}

        return JsonResponse(return_obj)


def getdates(request):
    return_obj = {
        'success': False
    }

    # Check if its an ajax post request
    if request.is_ajax() and request.method == 'GET':

        token = app.get_custom_setting('spt_access_token')
        api_url = app.get_custom_setting('spt_url') + '/api/GetAvailableDates/'

        region = request.GET.get('region')

        Session = app.get_persistent_store_database('primary_db', as_sessionmaker=True)
        session = Session()

        dbs = session.query(Regiondb).all()

        for db in dbs:
            if db.region == region:
                watershed = db.watershed
                subbasin = db.subbasin
                hostsite = db.host
                reach = db.spt_river

        session.close()

        request_headers = dict(Authorization="Token " + token)
        request_params = dict(watershed_name=watershed, subbasin_name=subbasin, reach_id=reach)
        res = requests.get(api_url, params=request_params, headers=request_headers)

        dates = ast.literal_eval(res.content)
        fulldate = []

        for date in dates:
            fulldate.append((date[:4] + "-" + date[4:6] + "-" + date[6:8], date))

        return_obj = {'success': True, 'datelist': fulldate}

    return JsonResponse(return_obj)
