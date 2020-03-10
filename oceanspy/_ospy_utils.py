# Instructions for developers:
# This modules collect useful functions used by OceanSpy.
# All functions here must be private (names start with underscore `_`)

# Import modules (can be public here)
import numpy
import warnings
import xgcm
import xarray as _xr


# =========
# FUNCTIONS
# =========
def _create_grid(dataset, coords, periodic, face_connections):
    """
    Create xgcm grid by adding comodo attributes to the
    dimensions of the dataset.

    Parameters
    ----------
    dataset: xarray.Dataset
    coords: dict
        E.g., {'Y': {Y: None, Yp1: 0.5}}
    periodic: list
        List of periodic axes.
    face_connections: dict
        dictionary specifying grid topology

    Returns
    -------
    grid: xgcm.Grid
    """
    # Clean up comodo (currently force user to specify axis using set_coords).
    for dim in dataset.dims:
        dataset[dim].attrs.pop('axis', None)
        dataset[dim].attrs.pop('c_grid_axis_shift', None)

    # Add comodo attributes.
    # TODO: it is possible to pass grid dict in xgcm.
    #       Should we implement it?
    warn_dims = []
    if coords:
        for axis in coords:
            for dim in coords[axis]:
                if dim not in dataset.dims:
                    warn_dims = warn_dims+[dim]
                else:
                    shift = coords[axis][dim]
                    dataset[dim].attrs['axis'] = axis
                    if shift:
                        dataset[dim].attrs['c_grid_axis_shift'] = str(shift)
    if len(warn_dims) != 0:
        warnings.warn("{} are not dimensions"
                      " and are not added"
                      " to the grid object.".format(warn_dims), stacklevel=2)
    # Create grid
    if face_connections is None:
        grid = xgcm.Grid(dataset, periodic=periodic)
    else:
        grid = xgcm.Grid(dataset, periodic=periodic, face_connections = face_connections)
    if len(grid.axes) == 0:
        grid = None

    return grid


def _check_instance(objs, classinfos):
    """
    Check if the object is an instance or subclass of classinfo class.

    Parameters
    ----------
    objs: dict
        {'obj_name': obj}
    classinfos: dict
        E.g.: {'obj_name': ['float', 'int']}
    """
    for key, value in objs.items():
        if isinstance(classinfos, str):
            classinfo = classinfos
        else:
            classinfo = classinfos[key]

        if isinstance(classinfo, str):
            classinfo = [classinfo]

        check = []
        for this_classinfo in classinfo:
            if '.' in this_classinfo:
                package = this_classinfo.split('.')[0]
                exec('import {}'.format(package))

            check = check + [eval('isinstance(value, {})'
                                  ''.format(this_classinfo))]

        if not any(check):
            raise TypeError("`{}` must be {}".format(key, classinfo))


def _check_oceanspy_axes(axes2check):
    """
    Check that axes are OceanSpy axes

    Parameters
    ----------
    axes2check: list
        List of axes
    """
    from oceanspy import OCEANSPY_AXES

    for axis in axes2check:
        if axis not in OCEANSPY_AXES:
            raise ValueError(_wrong_axes_error_message(axes2check))


def _check_list_of_string(obj, objName):
    """
    Check that object is a list of strings

    Parameters
    ----------
    obj: str or list
        Object to check
    objName: str
        Name of the object

    Returns
    -------
    obj: list
        List of strings
    """
    if obj is not None:
        obj = numpy.asarray(obj, dtype='str')
        if obj.ndim == 0:
            obj = obj.reshape(1)
        elif obj.ndim > 1:
            raise TypeError('Invalid `{}`'.format(objName))
    return obj


def _check_range(od, obj, objName):
    """
    Check values of a range, and return an object which is
    compatible with OceanSpy's functions.

    Parameters
    ----------
    od: OceanDataset
    obj: Range object
    objName: Name of the object

    Returns
    -------
    obj: Range object
    """
    if obj is not None:
        prefs = ['Y', 'X', 'Z', 'time']
        coords = ['YG', 'XG', 'Zp1', 'time']
        for _, (pref, coord) in enumerate(zip(prefs, coords)):
            if pref in objName:
                valchek = od._ds[coord]
                break
        obj = numpy.asarray(obj, dtype=valchek.dtype)
        if obj.ndim == 0:
            obj = obj.reshape(1)
        elif obj.ndim > 1:
            raise TypeError('Invalid `{}`'.format(objName))
        maxcheck = valchek.max().values
        mincheck = valchek.min().values
        if any(obj < mincheck) or any(obj > maxcheck):
            warnings.warn("\n{}Range of the oceandataset is: {}"
                          "\nRequested {} has values outside this range."
                          "".format(pref, [mincheck, maxcheck], objName),
                          stacklevel=2)
    return obj


def _handle_aliased(od, aliased, varNameList):
    """
    Return OceanSpy reference name and corresponding alises.

    Parameters
    ----------
    od: OceanDataset
    aliased: bool
    varNameList: list
        List of variables name

    Returns
    -------
    varNameListIN: list
        List of OceanSpy reference names
    varNameListOUT: list
        List of aliased names
    """
    if aliased:
        varNameListIN = _rename_aliased(od, varNameList)
    else:
        varNameListIN = varNameList
    varNameListOUT = varNameList
    return varNameListIN, varNameListOUT


def _rename_aliased(od, varNameList):
    """
    Check if there are aliases,
    and return the name of variables in the private dataset.
    This is used by smart-naming functions,
    where user asks for aliased variables.

    Parameters
    ----------
    od: OceanDataset
        oceandataset to check for missing variables
    varNameList: 1D array_like, str
        List of variables (strings).

    Returns
    -------
    varNameListIN: list of variables
        List of variable name to use on od._ds
    """

    # Check parameters
    _check_instance({'od': od}, 'oceanspy.OceanDataset')

    # Check if input is a string
    if isinstance(varNameList, str):
        isstr = True
    else:
        isstr = False

    # Move to numpy array
    varNameList = _check_list_of_string(varNameList, 'varNameList')

    # Get _ds names
    if od._aliases_flipped is not None:
        varNameListIN = [od._aliases_flipped[varName]
                         if varName in od._aliases_flipped
                         else varName for varName in list(varNameList)]
    else:
        varNameListIN = varNameList

    # Same type of input
    if isstr:
        varNameListIN = varNameListIN[0]

    return varNameListIN


def _check_mean_and_int_axes(od, meanAxes, intAxes, exclude):
    """
    Check and return mean and integral axes
    when they can be used together (e.g., for plots).

    Parameters
    ----------
    od: OceanDataset
    meanAxes: list, bool, or str
    intAxes: list, bool, or str
    exclude: list
        List of axes to exclude

    Returns
    -------
    meanAxes: list
    intAxes: list
    """
    # Check type
    _check_instance({'meanAxes': meanAxes,
                     'intAxes': intAxes,
                     'exclude': exclude},
                    {'meanAxes': ['bool', 'list', 'str'],
                     'intAxes': ['bool', 'list', 'str'],
                     'exclude': 'list'})
    if not isinstance(meanAxes, bool):
        meanAxes = _check_list_of_string(meanAxes, 'meanAxes')
    if not isinstance(intAxes, bool):
        intAxes = _check_list_of_string(intAxes, 'intAxes')

    # Check both True
    check1 = (meanAxes is True and intAxes is not False)
    check2 = (intAxes is True and meanAxes is not False)
    if check1 or check2:
        raise ValueError('If one between `meanAxes` and `intAxes` is True,'
                         ' the other must be False')

    # Get axes to pass
    if meanAxes is True:
        meanAxes = [coord
                    for coord in od.grid_coords
                    if coord not in exclude]
    elif not isinstance(meanAxes, bool):
        if any([axis in exclude for axis in meanAxes]):
            raise ValueError('These axes can not be in `meanAxes`:'
                             ' {}'.format(exclude))

    if intAxes is True:
        intAxes = [coord
                   for coord in od.grid_coords
                   if coord not in exclude]
    elif not isinstance(intAxes, bool):
        if any([axis in exclude for axis in intAxes]):
            raise ValueError('These axes can not be in `intAxes`:'
                             ' {}'.format(exclude))

    return meanAxes, intAxes


def _rename_coord_attrs(ds):
    """
    to_netcdf and to_zarr don't like coordinates attribute

    Parameters
    ----------
    ds: xarray.Dataset

    Returns
    -------
    ds: xarray.Dataset
    """

    for var in ds.variables:
        attrs = ds[var].attrs
        coordinates = attrs.pop('coordinates', None)
        ds[var].attrs = attrs
        if coordinates is not None:
            ds[var].attrs['_coordinates'] = coordinates
    return ds


def _restore_coord_attrs(ds):
    """
    Put back coordinates attribute that
    to_netcdf and to_zarr didn't like.

    Parameters
    ----------
    ds: xarray.Dataset

    Returns
    -------
    ds: xarray.Dataset
    """

    for var in ds.variables:
        attrs = ds[var].attrs
        coordinates = attrs.pop('_coordinates', None)
        ds[var].attrs = attrs
        if coordinates is not None:
            ds[var].attrs['coordinates'] = coordinates
    return ds

# ========
# POP Model Output
# ========

def _add_pop_dims_to_dataset(ds):
    ds_new = ds.copy()
    ds_new['XU'] = _xr.Variable(('XU'), np.arange(len(ds.nlon)) + 1, {'axis': 'X', 'c_grid_axis_shift': 0.5})
    ds_new['YU'] = _xr.Variable(('YU'), np.arange(len(ds.nlat)) + 1, {'axis': 'Y', 'c_grid_axis_shift': 0.5})
    ds_new['XT'] = _xr.Variable(('XT'), np.arange(len(ds.nlon)) + 0.5, {'axis': 'X'})
    ds_new['XT'] = _xr.Variable(('XT'), np.arange(len(ds.nlat)) + 0.5, {'axis': 'Y'})

    # add metadata to z grid
    ds_new=ds_new.set_coords({'z_t','z_w','z_w_top','z_w_bot'})
    ds_new['Z_t'].attrs.update({'axis': 'Z'})
    ds_new['Z_w'].attrs.update({'axis': 'Z', 'c_grid_axis_shift': -0.5})
    ds_new['Z_w_top'].attrs.update({'axis': 'Z', 'c_grid_axis_shift': -0.5})
    ds_new['Z_w_bot'].attrs.update({'axis': 'Z', 'c_grid_axis_shift': 0.5})

    return ds_new


def _dims_from_grid_loc(grid_loc):
    grid_loc = str(grid_loc)
    ndim = int(grid_loc[0])
    x_loc_key = int(grid_loc[1])
    y_loc_key = int(grid_loc[2])
    z_loc_key = int(grid_loc[3])

    x_loc = {1: 'XT', 2: 'XU'}[x_loc_key]
    y_loc = {1: 'XT', 2: 'XU'}[y_loc_key]
    z_loc = {0: 'surface', 1: 'z_t', 2: 'z_w'}[z_loc_key]

    if ndim == 3:
        if z_loc == 'surface':
            return y_loc, x_loc
        else:
            return z_loc, y_loc, x_loc
    elif ndim == 2 :
        return z_loc, y_loc, x_loc


def _label_coord_grid_locs(ds):
    ''' Assign grid loc to label coordinates for each variables. grid_loc consists of 4 numbers grid_loc=abcd, where
        a: ndim
        b: x_loc
        c: y_loc
        d: z_loc
    Examples:
        2D variables:
            2220: nlat_u, nlon_u
            2210: nlat_t, nlon_u
            2120: nlat_u, nlon_t
            2110: nlat_t, nlon_t
        3D variables
            3121: z_t,nlat_u,nlon_u
            3111: z_t,nlat_t, nlon_t
            3211: z_w,nlat_t,nlon_t
    '''
    grid_locs = {'ANGLE': '2220', 'ANGLET': '2110',
                 'DXT': '2110', 'DXU': '2220',
                 'DYT': '2110', 'DYU': '2220',
                 'HT': '2110', 'HU': '2220',
                 'HTE': '2210', 'HTN': '2120',
                 'HUS': '2210', 'HUW': '2120',
                 'KMT': '2110', 'KMU': '2220',
                 'REGION_MASK': '2110',
                 'TAREA': '2110', 'TLAT': '2110', 'TLONG': '2110',
                 'UAREA': '2220', 'ULAT': '2220', 'ULONG': '2220',
                 'ADVU': '3221', 'ADVV': '3221',
                 'DIA_IMPVF_SALT': '3112', 'DIA_IMPVF_TEMP': '3112',
                 'EVAP_F': '2110', 'GRADX': '3221', 'GRADY': '3221',
                 'HBLT': '2110', 'HMXL': '2110',
                 'HDIFB_SALT': '3112', 'HDIFB_TEMP': '3112',
                 'HDIFE_SALT': '3211', 'HDIFE_TEMP': '3211',
                 'HDIFN_SALT': '3121', 'HDIFN_TEMP': '3121',
                 'HDIFFU': '3221', 'HDIFFV': '3221',
                 'KPP_SRC_SALT': '3111', 'KPP_SRC_TEMP': '3111',
                 'LWDN_F': '2110', 'LWUP_F': '2110',
                 'MELTH_F': '2110', 'MELT_F': '2110',
                 'PD': '3111', 'PREC_F': '2110', 'QFLUX': '2110',
                 'QSW_3D': '3111', 'ROFF_F': '2110', 'SALT': '3111',
                 'SALT_F': '2110', 'SENH_F': '2110', 'SFWF': '2110',
                 'SFWF_WRST': '2110', 'SHF': '2110', 'SHF_QSW': '2110',
                 'SNOW_F': '2110', 'SSH': '2110', 'SSH2': '2110',
                 'SU': '2220', 'SV': '2220', 'TAUX': '2220', 'TAUY': '2220',
                 'TBLT': '2110', 'TEMP': '3111', 'TEND_TEMP': '3111',
                 'TEND_SALT': '3111', 'TMXL': '2110',
                 'UES': '3211', 'UET': '3211', 'UV': '3221',
                 'UVEL': '3221', 'UVEL2': '3221',
                 'VVEL': '3221', 'VVEL2': '3221',
                 'VDIFFU': '3221', 'VDIFFV': '3221',
                 'VNS': '3121', 'VNT': '3121',
                 'WTS': '3112', 'WTT': '3112', 'WVEL': '3222',
                 'XBLT': '2110', 'XMXL': '2110'}
    ds_new = ds.copy()
    for var in ds_new.variables:
        if var in grid_locs.keys():
            ds_new[var].attrs['grid_loc'] = grid_locs[var]
    return ds_new


def _relabel_pop_dims(ds):
    """Return a new xarray dataset with distinct dimensions for variables at
    different grid points.
    """
    ds_new = _label_coord_grid_locs(ds)
    ds_new = _add_pop_dims_to_dataset(ds_new)
    for vname in ds_new.variables:
        if 'grid_loc' in ds_new[vname].attrs:
            da = ds_new[vname]
            dims_orig = da.dims
            new_spatial_dims = _dims_from_grid_loc(da.attrs['grid_loc'])
            if dims_orig[0] == 'Nt':
                dims = ('Nt',) + new_spatial_dims
            else:
                dims = new_spatial_dims
            ds_new[vname] = _xr.Variable(dims, da.data, da.attrs, da.encoding, fastpath=True)
    return ds_new


# ========
# MESSAGES
# ========
def _check_part_position(od, InputDict):
    for InputName, InputField in InputDict.items():
        if 'time' in InputName:
            InputField = numpy.asarray(InputField, dtype=od._ds['time'].dtype)
            if InputField.ndim == 0:
                InputField = InputField.reshape(1)
            ndim = 1
        else:
            InputField = numpy.asarray(InputField)
            if InputField.ndim < 2 and InputField.size == 1:
                InputField = InputField.reshape((1, InputField.size))
            ndim = 2
        if InputField.ndim > ndim:
            raise TypeError('Invalid `{}`'.format(InputName))
        else:
            InputDict[InputName] = InputField
    return InputDict


def _check_ijk_components(od, iName=None, jName=None, kName=None):
    ds = od._ds
    for _, (Name, dim) in enumerate(zip([iName, jName, kName],
                                        ['Xp1', 'Yp1', 'Zl'])):
        if Name is not None and dim not in ds[Name].dims:
            raise ValueError('[{}] must have dimension [{}]'.format(Name, dim))


def _check_native_grid(od, func_name):
    wrong_dims = ['mooring', 'station', 'particle']
    for wrong_dim in wrong_dims:
        if wrong_dim in od._ds.dims:
            raise ValueError('`{}` cannot subsample {} oceandatasets'
                             ''.format(func_name, wrong_dims))


def _check_options(name, selected, options):
    if selected not in options:
        raise ValueError('`{}` [{}] not available.'
                         ' Options are: {}'.format(name, selected, options))


def _ax_warning(kwargs):
    ax = kwargs.pop('ax', None)
    if ax is not None:
        warnings.warn("\n`ax` can not be provided for animations. "
                      "This function will use the current axis", stacklevel=2)
    return kwargs


def _wrong_axes_error_message(axes2check):
    from oceanspy import OCEANSPY_AXES
    return ("{} contains non-valid axes."
            " OceanSpy axes are: {}").format(axes2check, OCEANSPY_AXES)


def _setter_error_message(attribute_name):
    return "Set new `{}` using .set_{}".format(attribute_name, attribute_name)
