"""Creates Sync Box remote entity."""

import json
import logging
import os
import requests

from homeassistant.components import remote
from homeassistant.helpers import config_validation
from homeassistant.helpers import entity_platform
from homeassistant import util

from . import api
from . import const
from . import schemas

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
  """Adds Philips Hue Sync Box to the list of remotes."""

  _LOGGER.info('Setting up remotes for Hue Sync Box.')

  platform = entity_platform.current_platform.get()

  platform.async_register_entity_service(
      const.SERVICE_GET_ACCESS_TOKEN,
      schemas.GET_ACCESS_TOKEN_SCHEMA,
      const.SERVICE_GET_ACCESS_TOKEN,
  )

  platform.async_register_entity_service(
      const.SERVICE_SET_BRIGHTNESS,
      schemas.SET_BRIGHTNESS_SCHEMA,
      const.SERVICE_SET_BRIGHTNESS,
  )

  platform.async_register_entity_service(
      const.SERVICE_SET_HDMI_INPUT,
      schemas.SET_HDMI_INPUT_SCHEMA,
      const.SERVICE_SET_HDMI_INPUT,
  )

  platform.async_register_entity_service(
      const.SERVICE_SET_INTENSITY,
      schemas.SET_INTENSITY_SCHEMA,
      const.SERVICE_SET_INTENSITY,
  )

  platform.async_register_entity_service(
      const.SERVICE_SET_SYNC_MODE,
      schemas.SET_SYNC_MODE_SCHEMA,
      const.SERVICE_SET_SYNC_MODE,
  )

  async_add_entities([HueSyncBoxRemote(config, hass)], True)

  return True


class HueSyncBoxRemote(remote.RemoteDevice):
  """Representation of a Sync Box remote service.

  Properties:
    attributes: Device attributes. See below.
    entity_id: The Entity id of this remote.
    is_on: Whether the sync box is on.
    state: Current on/off state of the syncing status.

  Attributes:
    brightness: Brightness of the lights.
    hdmi_active: Whether HDMI input is active.
    hdmi_source: HDMI Input selected.
    inputs:
      input1: Input 1 name.
      input2: Input 2 name.
      input3: Input 3 name.
      input4: Input 4 name.
    intensity: Intensity of current mode.
    name: Name of the sync box.
    sync_active: Whether syncing is active.
    sync_mode: Syncing mode state.

  Services:
    get_access_token: Gets access token.
    set_brightness: Sets brightness.
    set_hdmi_input: Sets HDMI input.
    set_intensity: Sets intensity for current mode.
    set_sync_mode: Sets Sync mode.
    toggle: Toggles active sync.
    turn_off: Turns off active sync.
    turn_on: Turns on active sync.
    update: Updates Sync Box details.
  """

  def __init__(self, config, hass):
    """Initializes the remote."""
    _LOGGER.info(
        f'Started Hue Sync Box for IP {config.get(const.CONF_IP_ADDRESS)}')
    self._config = config
    self._hass = hass

    # Config attributes.
    self._ip_address = config.get(const.CONF_IP_ADDRESS)
    self._name = config.get(const.CONF_NAME, const.DEVICE_DEFAULT_NAME)
    self._entity_id = util.slugify(self._name)

    # API interactions.
    self._token_file_name = const.TOKEN_FILE.format(self._entity_id)
    self._access_token = None
    self._entity_onboarding = False
    self._api = api.HueSyncBoxApi(self._ip_address, self._access_token)

    # Internal attributes.
    self._brightness = None
    self._device_name = const.DEVICE_DEFAULT_NAME
    self._hdmi_active = None
    self._hdmi_source = None
    self._input1 = None
    self._input2 = None
    self._input3 = None
    self._input4 = None
    self._intensity = None
    self._intensities = None
    self._sync_active = None
    self._sync_mode = None

    _LOGGER.debug(f'Set up for {self._entity_id} completed.')

  # API token set up.
  def _get_access_token_data_from_file(self):
    """Gets access token from the file."""
    _LOGGER.debug(f'Getting token from file: {self._token_file_name}.')

    token_file = self._hass.config.path(self._token_file_name)

    if not os.path.isfile(token_file):
      return None

    with open(token_file, 'r') as token_file_content:
      token_data = json.loads(token_file_content.read()) or {}

    _LOGGER.debug(f'Token data found on file: {self._token_file_name}.')

    return token_data.get('access_token')

  def _store_access_token(self, access_token):
    """Stores access token into file.

    Args:
      access_token: String containing access token.
    """
    access_token_json = {'access_token': access_token}
    with open(self._token_file_name, 'w+') as token_file:
      token_file.write(json.dumps(access_token_json))

  # Properties.
  @property
  def entity_id(self):
    """Returns the entity ID for this remote."""
    return f'remote.{self._entity_id}'

  @property
  def is_on(self):
    """Returns true if Sync Box sync is on."""
    return self._hdmi_active

  @property
  def name(self):
    """Returns the display name of this Sync Box."""
    return self._name or self._device_name

  @property
  def state(self):
    """Returns on/off sync state of Sync Box."""
    return 'on' if self.is_on else 'off'

  # Attributes.
  @property
  def device_state_attributes(self):
    """Return the state attributes."""
    return {
        'brightness': self._brightness,
        'device_name': self._device_name,
        'hdmi_active': self._hdmi_active,
        'hdmi_source': self._hdmi_source,
        'inputs': {
            'input1': self._input1,
            'input2': self._input2,
            'input3': self._input3,
            'input4': self._input4,
        },
        'intensity': self._intensity,
        'intensities': self._intensities,
        'sync_active': self._sync_active,
        'sync_mode': self._sync_mode,
    }

  # Services.
  def get_access_token(self):
    """Gets access token. If file does not exist, initializes process."""
    _LOGGER.debug('Getting access token for Philips Hue Sync Box.')

    if self._access_token:
      return self._access_token

    if not self._name or self._name == 'None':
      _LOGGER.debug('Entity with no name was tried. Blocking request.')
      return

    access_token = self._get_access_token_data_from_file()
    if access_token:
      _LOGGER.debug('Token file content found.')
      self._access_token = access_token
      self._api.set_access_token(access_token)
      return access_token

    access_token = self._api.request_access_token(self._name)
    if access_token:
      _LOGGER.debug('Token file request successful.')
      self._access_token = access_token
      self._store_access_token(access_token)
      self._hass.components.persistent_notification.create(
          f'Access token for Philips Hue Sync Box {self._entity_id} '
          f'successfully obtained: {access_token}.',
          title=self._name,
          notification_id=f'hue_sync_box_setup_{self._entity_id}')
      return access_token

    self._hass.components.persistent_notification.create(
        'No token authentication found for Philips Hue Sync Box '
        f'"{self._name}". In order to authorize Home-Assistant to use your '
        'Philips Hue Sync Box, call hue_sync_box.get_access_token for this '
        'entity. Within 5 seconds, press the off button during 3 seconds '
        'until the on/off light blinks green. Then, call the service '
        'hue_sync_box.get_access_token for this entity again within 5 '
        'seconds.',
        title=self._name,
        notification_id=f'hue_sync_box_setup_{self._entity_id}')
    self._entity_onboarding = True

  def set_brightness(self, brightness):
    """Sets HDMI Sync Box to a certain brightness.

    Args:
      brightness: Brightness of the light during sync.
    """
    self._api.set_brightness(brightness)
    self.update()

  def set_hdmi_input(self, hdmi_input):
    """Sets HDMI Sync box to a certain HDMI input.

    Args:
      hdmi_input: HDMI input number.
    """
    self._api.set_hdmi_input(hdmi_input)
    self.update()

  def set_intensity(self, intensity, sync_mode=None):
    """Sets HDMI Sync Box to a certain intensity mode

    Args:
      intensity: Intensity level.
      sync_mode: Mode of which to set up intensity.
    """
    if not sync_mode:
      self.update()
      sync_mode = self._sync_mode

    self._api.set_intensity(intensity, sync_mode)
    self.update()

  def set_sync_mode(self, sync_mode):
    """Sets HDMI Sync Box to a certain sync mode.

    Args:
      sync_mode: Sync mode to which to set up Sync box.
    """
    self._api.set_sync_mode(sync_mode)
    self.update()

  def toggle(self):
    """Turns on or off depending on status."""
    _LOGGER.debug(f'Toggling based on status {self._hdmi_active}.')
    self.update()

    if self._hdmi_active is True:
      self.turn_off()
    else:
      self.turn_on()

    self.update()

  def turn_off(self):
    """Turns off."""
    self.set_sync_mode('powersave')
    self.update()

  def turn_on(self):
    """Turns on."""
    self.set_sync_mode('passthrough')
    self.update()

  def update(self):
    """Updates device status."""
    if self._entity_onboarding and not self._access_token:
      _LOGGER.debug(
          f'Hue Sync Box {self._entity_id} needs to get onboarded before '
          'updating.')
      return

    if not self._access_token:
      self.get_access_token()

    if not self._access_token:
      return

    if self._entity_onboarding:
      self._entity_onboarding = False

    info = self._api.get_device_details()

    device = info.get('device', {})
    self._device_name = device.get('name', const.DEVICE_DEFAULT_NAME)

    execution = info.get('execution', {})
    self._brightness = execution.get('brightness', const.DEFAULT_STR_VALUE)
    self._hdmi_active = execution.get('hdmiActive', const.DEFAULT_STR_VALUE)
    self._hdmi_source = execution.get('hdmiSource', const.DEFAULT_STR_VALUE)
    self._sync_active = execution.get('syncActive', const.DEFAULT_STR_VALUE)
    self._sync_mode = execution.get('mode', const.DEFAULT_STR_VALUE)

    video = execution.get('video', {})
    game = execution.get('game', {})
    music = execution.get('music', {})
    self._intensities = {
        'video': video.get('intensity'),
        'game': game.get('intensity'),
        'music': music.get('intensity'),
    }
    self._intensity = (
        self._intensities[self._sync_mode]
        if self._sync_mode in self._intensities
        else 'off'
    )

    hdmi = info.get('hdmi', {})
    input1 = hdmi.get('input1', {})
    self._input1 = input1.get('name', 'HDMI 1')
    input2 = hdmi.get('input2', {})
    self._input2 = input2.get('name', 'HDMI 2')
    input3 = hdmi.get('input3', {})
    self._input3 = input3.get('name', 'HDMI 3')
    input4 = hdmi.get('input4', {})
    self._input4 = input4.get('name', 'HDMI 4')
