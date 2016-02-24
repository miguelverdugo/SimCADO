###############################################################################
# LightObject
#
# DESCRIPTION
# The LightObject is essentially a list of spectra and a list of positions. The
# list of positions contains a reference to the relevant spectra. The advantage
# here is that if there are repeated spectra in a data cube, we can reduce the
# amount of calculations needed. Furthermore, if the input is originally a list
# of stars, etc where the position of a star is not always and integer multiple
# of the plate scale, we can keep the information until the PSFs are needed.
#
# The LightObject contains two arrays:
#  - PositionArray:
#  - SpectrumArray


# Flow of events
# - Generate the lists of spectra and positions
# - Apply the transmission curves [SpectrumArray]
# - shrink the 1D spectra to the resolution of the PSFCube layers [SpectrumArray]
# - apply any 2D PlaneEffects [PositionArray]
# for i in len(slices)
#   - generate a working slice [PositionArray, SpectrumArray, WorkingSlice]
#   - Apply the PSF for the appropriate wavelength [WorkingSlice]
#   - Apply any wavelength dependent PlaneEffects [WorkingSlice]
#   - apply Poisson noise to the photons in the slice [WorkingSlice]
#   - add the WorkingSlice to the FPA [WorkingSlice, FPArray]


## TODO implement conversions to Source object from:
#ascii
#    x,y,mag,[temp]
#    x,y,type
#images
#    JHK
#    cube


import os
import warnings

import numpy as np
import scipy.ndimage.interpolation as spi

from astropy.io import fits
from astropy.convolution import convolve, convolve_fft

class LightObject(object):

    def __init__(self, source, cmds):
        """
        Keywords:
        - lam: [um] an array of size L with wavelengths for the spectra
        - spectra: [photons] a 2D array of size (S,L) with a spectrum for S
                    unique sources
        - x, y: [pix] arrays of size N holding the pixel coordinate information
                for N sources

        Optional keywords:
        - spec_ref: [int] an array holding N references joining each of the N
                    source pixel coordinates to one of the S unique spectra
                    max(spec_ref) < spectra.shape[0]
        - weights: [float] an array of size N with weights for each source
        """
        self.params = cmds
        self.size = 4096

        self.info = dict([])
        self.info['created'] = 'yes'
        self.info['description'] = "List of spectra and their positions"

        self.lam        = source.lam
        self.spectra    = source.spectra
        self.x_orig     = source.x
        self.y_orig     = source.y
        self.spec_ref   = source.spec_ref
        self.weight     = source.weight
        self.x, self.y  = deepcopy(self.x_orig), deepcopy(y_orig)

        # add a second dimension to self.spectra so that all the 2D calls work
        if len(self.spectra.shape) == 1:
            self.spectra.shape = np.asarray([self.spectra.shape]*2)

        self.array = np.zeros((self.size, self.size), dtype=np.float32)

    def __str__(self):
        return self.info['description']

    def __array__(self):
        return self.array

    def __getitem__(self, i):
        return self.x[i], self.y[i], \
                            self.spectra[self.spec_ref[i],:] * self.weight[i]

    def shrink_to_detector(self):
        """
        Contract the oversampled photon array down to one that is consistent
        with the pixel scale of the FPA
        """
        pass


    def poissonify(self, arr=None):
        """
        Add a realisation of the poisson process to the array 'arr'.
        If arr=None, the poisson realisation is applied to LightObject.array

        Optional keyword:
        - arr:
        """
        if arr is None:
            self.array = np.random.poisson(self.array).astype(np.float32)
        else:
            return np.random.poisson(arr).astype(np.float32)


    def add_uniform_background(self, emission_curve, lam_min, lam_max,
                                                                output=False):
        """
        Take an EmissionCurve and some wavelength boundaries, lam_min lam_max,
        and sum up the photons in between. Add those to the LightObject array.

        Keywords:
        - emission_curve: EmissionCurve object with background emission photons
        - lam_min, lam_max: the wavelength limits

        Optional keywords:
        - output: [False, True] if output is True, the BG emission array is
                  returned
        """
        bg_photons = emission_curve.photons_in_range(lam_min, lam_max)

        if output is True:
            return bg_photons * np.ones((self.size, self.size), dtype=np.float32)
        else:
            self.array += bg_photons


    def apply_psf(self, psf, lam_min, lam_max, sub_pixel=False):
        """

        """
        slice_photons = self.get_slice_photons(lam_min, lam_max, zoom=10)
        slice_array = np.zeros((self.size, self.size), dtype=np.float32)

        # if sub pixel accuracy is needed, be prepared to wait. For this we
        # need to go through every source spectra in turn, shift the psf by
        # the decimal amount given by pos - int(pos), then place the a
        # certain slice of the psf on the output array.
        if sub_pixel:
            x_int, y_int = self.x.astype(int), self.y.astype(int)
            dx, dy = self.x - x_int, self.y - y_int
            ax, ay = np.array(slice_array.shape) // 2
            bx, by = np.array(psf.array.shape)   // 2

            # for each point source in the list, add a psf to the slice_array
            for i in range(len(slice_photons)):
                psf_tmp = spi.shift(psf.array, (dx[i],dy[i]), order=1)
                x_pint, y_pint = x_int[i], y_int[i]

                # Find the slice borders for the array where the psf will go
                ax0 = np.max(np.array((x_pint - bx, [0]*len(x_pint))), axis=0)
                ax1 = np.min(np.array((x_pint + bx + 1,
                                 [slice_array.shape[0]]*len(x_pint))), axis=0)
                ay0 = np.max(np.array((y_pint - by, [0]*len(y_pint))), axis=0)
                ay1 = np.min(np.array((y_pint + by + 1,
                                 [slice_array.shape[1]]*len(y_pint))), axis=0)

                # the slice limits of the psf array are found by taking the
                # pixel distance from the x,y position to the slice limits
                # of the slice_array. This distance is subtracted from the
                # centre of the psf array.
                bx0 = bx - (x_pint - ax0)
                bx1 = bx + (ax1 - x_pint)
                by0 = by - (y_pint - ay0)
                by1 = by + (ay1 - y_pint)

                slice_array[ax0:ax1, ay0:ay1] = psf.array[bx0:bx1, by0:by1] \
                                        * slice_photons[p] * self.weights[p]

        else:
            # If astrometric precision is not that important and everything
            # has been oversampled, use this section.

            slice_array[x_int, y_int] = slice_photons * self.weights
            slice_array = convolve_fft(slice_array, psf.array)

        return slice_array



    def apply_plane_effect(self, plane):
        pass


    def apply_transmission_curve(self, transmission_curve):
        """
        Apply the values from a TransmissionCurve object to self.spectra

        Keywords:
        - transmission_curve: The TransmissionCurve to be applied
        """
        tc = transmission_curve
        tc.resample(self.lam)
        self.spectra *= tc.val

    def get_slice_photons(self, lam_min, lam_max, zoom = 10):
        """
        Caluclate how many photons for each source exist in the wavelength bin
        defined by lam_min and lam_max.

        Keywords:

        Optional keywords:
        - zoom
        """
        # Check if the slice limits are within the spectrum wavelength range
        if lam_min > self.lam[-1] or lam_max < self.lam[0]:
            print((lam_min, lam_max), (self.lam[0], self.lam[-1]))
            raise ValueError("lam_min or lam_max outside wavelength range" + \
                                                                "of spectra")

        # find the closest indices i0, i1 which match the limits
        x0, x1 = np.abs(self.lam - lam_min), np.abs(self.lam - lam_max)
        i0 = np.where(x0 == np.min(x0))[0][0]
        i1 = np.where(x1 == np.min(x1))[0][0]
        if self.lam[i0] > lam_min and i0 > 0:
            i0 -= 1
        if self.lam[i1] < lam_max and i1 < len(self.lam):
            i1 += 1

        n_bins = zoom * (i1 - i0)
        lam_zoom  = np.linspace(lam_min, lam_max, n_bins)
        spec_zoom = np.zeros((self.spectra.shape[0], len(lam_zoom)))

        # spec_zoom = np.asarray([np.interp(lam_zoom, lam[i0:i1], spec[i0:i1])
        # for spec in spectra])
        for i in range(len(self.spectra)):
            spec_zoom[i,:] = np.interp(lam_zoom, self.lam[i0:i1],
                                                        self.spectra[i,i0:i1])

        slice_photons = np.sum(spec_zoom, axis=1)
        return slice_photons

    def to_ADU(self):
        """
        Convert the photons/electrons to ADU for reading out
        """
        return self.array * self.params["FPA_GAIN"]

    def __mul__(self, x):
        newlight = deepcopy(self)
        newlight.array *= x
        return newlight

    def __add__(self, x):
        newlight = deepcopy(self)
        newlight.array += x
        return newlight

    def __sub__(self, x):
        newlight = deepcopy(self)
        newlight.array -= x
        return newlight

    def __rmul__(self, x):
        return self.__mul__(x)

    def __radd__(self, x):
        return self.__add__(x)

    def __rsub__(self, x):
        return self.__mul__(-1) + x

    def __imul__(self, x):
        return self.__mul__(x)

    def __iadd__(self, x):
        return self.__add__(x)

    def __isub__(self, x):
        return self.__sub__(x)



class Source(object):
    """
    Source class generates the arrays needed for LightObject. It takes various
    inputs and converts them to an array of positions and references to spectra
    It also converts spectra to photons/s/voxel

    Keywords:
    - filename
    or
    - lam
    - spectra
    - x
    - y
    - spec_ref
    - weight
    """

    def __init__(self, pix_res, units, **kwargs):

        self.pix
        self.units = units



    def from_cube(self, lam, cube, units="ph/s/arcsec2/micron"):
        """
        Make a Source object from a cube in memory or a FITS cube on disk
        """
        self.units = units
        if type(cube) == str and os.path.exists(cube):
            cube = fits.getdata(cube)
            if "BUNIT" in cube.getheader().keys():
                self.units = cube.getheader["BUNIT"]

        flux_map = np.sum(cube, axis=0).astype(dtype=np.float32)
        x, y = np.where(flux_map != 0)

        self.lam = lam
        self.spec_arr = np.swapaxes(ipt[:,x,y], 0, 1)
        self.x, self.y = x,y
        self.ref = np.arange(len(x))
        self.weight = np.ones(len(x))

    def from_arrays(self, lam, spec_arr, x, y, ref, weight=None,
                    units="ph/s/arcsec2/micron"):
        """
        Make a Source object from a series of lists
        """

        self.lam = lam
        self.spec_arr = spec_arr
        self.x = x
        self.y = y
        self.ref = ref
        self.weight = weight   if weight is not None   else np.array([1]*len(x))
        self.units = units

        if len(spec_arr.shape) == 1:
            self.spec_arr = np.array((spec_arr, spec_arr))


    def read(self, filename="../input/GC2.fits", units="ph/s/arcsec2/micron"):
        """
        Read in a previously saved Source FITS file
        """
        self.units = units

        ipt = fits.open(filename)
        self.x = ipt[0].data[0,:]
        self.y = ipt[0].data[1,:]
        self.ref = ipt[0].data[2,:]
        self.weight = ipt[0].data[3,:]

        self.spec_arr = ipt[1].data
        lam_min, lam_max = ipt[1].header["LAM_MIN"], ipt[1].header["LAM_MAX"]
        self.lam = np.linspace(lam_min, lam_max, ipt[1].header["NAXIS1"])


    def write(self, filename="../input/source.fits"):
        """
        Just a place holder so that I know what's going on with the input table
        * The fist extension [0] contains an "image" of size 4 x N where N is the
        amount of sources. The 4 columns are x, y, spec_ref, weight.
        * The second extension [1] contains an "image" with the spectra of each
        source. The image is M x len(spectrum), where M is the number of unique
        spectra in the source list. max(spec_ref) = M - 1
        """

        hdr = fits.getheader("../../../PreSim/Input_cubes/GC2.fits")
        ipt = fits.getdata("../../../PreSim/Input_cubes/GC2.fits")
        flux_map = np.sum(ipt, axis=0).astype(dtype=np.float32)
        x,y = np.where(flux_map != 0)
        ref = np.arange(len(x))
        weight = np.ones(len(x))
        spec_arr = np.swapaxes(ipt[:,x,y], 0, 1)
        lam = np.linspace(0.2,2.5,231)

        xyHDU = fits.PrimaryHDU(np.array((x,y,ref,weight)))
        xyHDU.header["X_COL"] = "1"
        xyHDU.header["Y_COL"] = "2"
        xyHDU.header["REF_COL"] = "3"
        xyHDU.header["W_COL"] = "4"
        xyHDU.header["BUNIT"] = self.units
        xyHDU.header["SIM_CUBE"] = "SOURCE"
        #xyHDU.header["DISTANCE"] = (hdr["DISTANCE"], "Mpc")
        #xyHDU.header["RADIUS"] = (hdr["RADIUS"], "kpc")

        specHDU = fits.ImageHDU(spec_arr)
        specHDU.header["LAM_MIN"] = lam[0]
        specHDU.header["LAM_MAX"] = lam[-1]

        hdu = fits.HDUList([xyHDU, specHDU])
        hdu.writeto("",clobber=True)




    def arrays_to_light(lam, spectra, x, y, spec_ref, weights, pix_res, area):
        pass

    def image_to_light(filename):
        pass

    def ascii_to_light(filename):
        pass

    def fitscube_to_light(filename):
        pass

    def read_light():
        pass









###############################################################
# Old code from LightObject - not sure if I still need it.

# def apply_psf_cube(self, psf_cube, lam_bin_edges, export_slices=False,
                        # filename = "../output/slices.fits", sub_pixel=False):
        # """
        # For all PSFs in a PSFCube, generate an array containing the number of
        # photons expected in the wavelength range of that PSF, and where they
        # will land on the FOV. Then apply the PSF to this "ideal" FOV. Each layer
        # is added to the final LightObject array.

        # ??? Issue
        # 'zoom' for get_slice_photons is set at 10. Should this be variable?

        # Keywords:
        # - psf_cube: a PSFCube object containing all the PSFs to be applied
        # - lam_bin_edges: the edges of the wavelength bins used in the PSFCube

        # Optional keywords:
        # - sub_pixel: [False, True] simulate sources that aren't directly in the
                     # centre of a pixel
        # - export slices: [False, True] export all the slices to a fits file
        # """

        # if len(lam_bin_edges) != len(psf_cube) + 1:
            # warnings.warn("Number of PSFs does not fit to lam_bin_edges")

        # tmp_array = np.zeros((self.size, self.size), dtype=np.float32)

        # for i in range(len(psf_cube)):

            # psf = psf_cube[i]
            # lam_min, lam_max = lam_bin_edges[i], lam_bin_edges[i+1]

            # # add the slice_array to the final array
            # tmp_array += self.apply_psf(psf, lam_min, lam_max, sub_pixel=False)

            # # for debugging purposes, save the layers to disk
            # if export_slices:
                # if not os.path.exists(filename):
                    # hdu = fits.PrimaryHDU(slice_array)
                    # hdu.writeto(filename)
                # else:
                    # hdu = fits.open(filename, mode="append")
                    # hdu.append(fits.ImageHDU(slice_array))
                    # hdu.update_extend()
                    # hdu.flush()
                    # hdu.close()

        # # link the tmp_array to self.array
        # self.array = tmp_array
