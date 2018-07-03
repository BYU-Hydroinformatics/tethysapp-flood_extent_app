from tethys_sdk.base import TethysAppBase, url_map_maker
from tethys_sdk.app_settings import CustomSetting


class FloodExtentApp(TethysAppBase):
    """
    Tethys app class for Flood Extent App.
    """

    name = 'Flood Extent App'
    index = 'flood_extent_app:home'
    icon = 'flood_extent_app/images/flood.png'
    package = 'flood_extent_app'
    root_url = 'flood-extent-app'
    color = '#49639a'
    description = 'Place a brief description of your app here.'
    tags = ''
    enable_feedback = False
    feedback_emails = []

    def url_maps(self):
        """
        Add controllers
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (
            UrlMap(
                name='home',
                url='flood-extent-app',
                controller='flood_extent_app.controllers.home'
            ),
            UrlMap(
                name='createnetcdf',
                url='flood-extent-app/createnetcdf',
                controller='flood_extent_app.ajax_controllers.createnetcdf'
            ),
            UrlMap(
                name='createprobnetcdf',
                url='flood-extent-app/createprobnetcdf',
                controller='flood_extent_app.ajax_controllers.createprobnetcdf'
            ),
            UrlMap(
                name='displaydrainagelines',
                url='flood-extent-app/displaydrainagelines',
                controller='flood_extent_app.ajax_controllers.displaydrainagelines'
            ),
            UrlMap(
                name='displaywarningpts',
                url='flood-extent-app/displaywarningpts',
                controller='flood_extent_app.ajax_controllers.displaywarningpts'
            ),
            UrlMap(
                name='getdates',
                url='flood-extent-app/getdates',
                controller='flood_extent_app.ajax_controllers.getdates'
            ),
        )

        return url_maps

    def custom_settings(self):

        return (
            CustomSetting(
                name='tethys_staging_token',
                type=CustomSetting.TYPE_STRING,
                description='Unique tethys-staging token to access data from Streamflow Prediction Tool',
                required = True
            ),
            CustomSetting(
                name='tethys_token',
                type=CustomSetting.TYPE_STRING,
                description='Unique tethys token to access data from Streamflow Prediction Tool',
                required=True
            ),
            CustomSetting(
                name='thredds_folder',
                type=CustomSetting.TYPE_STRING,
                description='Flood Extent Thredds Directory (must contain geojson drainage lines, hand, rating curve, and catchments)',
                required = True
            ),
        )