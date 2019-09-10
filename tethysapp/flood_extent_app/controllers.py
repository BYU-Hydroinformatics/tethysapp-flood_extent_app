from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from tethys_sdk.gizmos import *
from .model import get_all_regions, add_new_region
from .app import FloodExtentApp as app


@login_required()
def home(request):
    """
    Controller for the app home page.
    """

    dateinput = SelectInput(name='dateinput',
                            options=[],
                            initial=[])

    removebutton = Button(display_text='Remove Layers',
                          name='remlayers',
                          attributes={"onclick": "removelayers()"})

    regions = get_all_regions()

    table_rows = []
    regionlist = [(" ", " ")]

    for region in regions:
        table_rows.append(
            (
                region.region, region.filename, region.watershed, region.subbasin, region.host, region.spt_river
            )

        )
        regionlist.append((region.region, region.filename))

    regions_table = DataTableView(
        column_names=('Region', 'File Name', 'Watershed', 'Subbasin', 'Host', 'SPT River', 'Delete Button'),
        rows=table_rows,
        searching=True,
        attributes={"id": "regiontable"}
    )

    regioninput = SelectInput(name='regioninput',
                              options=regionlist,
                              initial=[regionlist[0][0]])

    add_button = Button(
        display_text='Add Region',
        name='add-button',
        icon='glyphicon glyphicon-plus',
        style='success',
        attributes={"onclick": "openregionmodal()", "style": "margin-right:5px"},
        submit=True
    )

    view_button = Button(
        display_text='View Region',
        name='view-button',
        icon='glyphicon glyphicon-plus',
        style='success',
        attributes={"onclick": "openviewmodal()", "style": "margin-right:5px"},
        submit=True
    )

    addregion = TextInput(display_text='Region (what shows in dropdown)',
                          name='addregion',
                          placeholder='e.g. Dominican Republic',
                          )

    addfilename = TextInput(display_text='File Name (region name in preprocessed files)',
                            name='addfilename',
                            placeholder='e.g. dominicanrepublic',
                            )

    addwatershed = TextInput(display_text='Watershed (SPT watershed where region is located)',
                             name='addwatershed',
                             placeholder='e.g. Dominican Republic',
                             )

    addsubbasin = TextInput(display_text='Subbasin (SPT subbbasin where region is located)',
                            name='addsubbasin',
                            placeholder='National',
                            )

    addhost = TextInput(display_text='SPT Host (Streamflow Prediction Tool Website)',
                        name='addhost',
                        placeholder='e.g. tethys.byu.edu, tethys-staging.byu.edu',
                        )

    addsptriver = TextInput(display_text='SPT River (Any river within SPT watershed and subbasin from above)',
                            name='addsptriver',
                            placeholder='499',
                            attributes={"type": "number"}
                            )

    region = ''
    filename = ''
    watershed = ''
    subbasin = ''
    spt_river = ''
    host = ''

    region_error = ''
    filename_error = ''
    watershed_error = ''
    subbasin_error = ''
    spt_river_error = ''
    host_error = ''

    if request.POST and 'submit' in request.POST:

        has_errors = False
        region = request.POST.get('addregion')
        filename = request.POST.get('addfilename')
        watershed = request.POST.get('addwatershed')
        subbasin = request.POST.get('addsubbasin')
        spt_river = request.POST.get('addsptriver')
        host = request.POST.get('addhost')

        if not region:
            has_errors = True
            region_error = 'Region is required'

        if not watershed:
            has_errors = True
            watershed_error = 'Watershed is required'

        if not subbasin:
            has_errors = True
            subbasin_error = 'Subbasin is required'

        if not filename:
            has_errors = True
            filename_error = 'Filename is required'

        if not host:
            has_errors = True
            host_error = 'Host is required'

        if not spt_river:
            has_errors = True
            spt_river_error = 'SPT River is required'

        if not has_errors:
            add_new_region(region, filename, watershed, subbasin, host, spt_river)
            return redirect(reverse('flood_extent_app:home'))

        messages.error(request, "Please fix errors.")

    context = {
        'dateinput': dateinput,
        'removebutton': removebutton,
        'regioninput': regioninput,
        'add_button': add_button,
        'view_button': view_button,
        'addregion': addregion,
        'addfilename': addfilename,
        'addwatershed': addwatershed,
        'addsubbasin': addsubbasin,
        'addsptriver': addsptriver,
        'regions_table': regions_table,
        'addhost': addhost,
        'thredds_url': app.get_custom_setting('thredds_url')
    }

    return render(request, 'flood_extent_app/home.html', context)
