# actually for Source2
import pytest

import os
import inspect

import numpy as np

from astropy.io import fits
from astropy.io import ascii as ioascii
from astropy.table import Table
from astropy import units as u
from astropy import wcs

from synphot import SourceSpectrum, SpectralElement
from synphot.models import Empirical1D
from synphot.units import PHOTLAM

import simcado as sim
from simcado.source import source2_utils
from simcado.source.source2 import Source
from simcado.source import source2 as src2
from simcado.optics.image_plane import ImagePlane
from simcado.utils import convert_table_comments_to_dict


def mock_dir():
    cur_dirname = os.path.dirname(inspect.getfile(inspect.currentframe()))
    rel_dirname = "mocks/sources/"
    return os.path.abspath(os.path.join(cur_dirname, rel_dirname))


MOCK_DIR = mock_dir()
sim.rc.__search_path__.insert(0, MOCK_DIR)


@pytest.fixture(scope="module")
def input_files():
    filenames = ["test_image.fits", "test_table.fits", "test_table.tbl",
                 "test_spectrum_Flam.dat", "test_spectrum_photlam.dat"]
    filenames = [os.path.join(MOCK_DIR, fname) for fname in filenames]
    return filenames


@pytest.fixture(scope="module")
def input_hdulist():
    filenames = ["test_image.fits"]
    filenames = [os.path.join(MOCK_DIR, fname) for fname in filenames]
    hdu_handle = fits.open(filenames[0])

    return hdu_handle


@pytest.fixture(scope="module")
def input_tables():
    filenames = ["test_table.fits", "test_table.tbl"]
    filenames = [os.path.join(MOCK_DIR, fname) for fname in filenames]
    tbls = []
    tbls += [Table.read(filenames[0])]
    tbls += [Table.read(filenames[1], format="ascii.basic")]
    tbls[1].meta.update(convert_table_comments_to_dict(tbls[1]))

    return tbls


@pytest.fixture(scope="module")
def input_spectra():
    filenames = ["test_spectrum_photlam.dat", "test_spectrum_Flam.dat"]
    filenames = [os.path.join(MOCK_DIR, fname) for fname in filenames]
    tbls = [ioascii.read(fname) for fname in filenames]
    specs = []
    for tbl in tbls:
        tbl.meta.update(convert_table_comments_to_dict(tbl))
        wave = tbl["wavelength"] * u.Unit(tbl.meta["wavelength_unit"])
        flux = tbl["flux"] * u.Unit(tbl.meta["flux_unit"])
        specs += [SourceSpectrum(Empirical1D, points=wave, lookup_table=flux)]

    return specs


@pytest.fixture(scope="function")
def table_source():
    n = 100
    unit = u.Unit("ph s-1 m-2 um-1")
    wave = np.linspace(0.5, 2.5, n) * u.um
    specs = [SourceSpectrum(Empirical1D, points=wave,
                            lookup_table=4 * np.ones(n) * unit),
             SourceSpectrum(Empirical1D, points=wave,
                            lookup_table=np.linspace(0, 4, n) * unit),
             SourceSpectrum(Empirical1D, points=wave,
                            lookup_table=np.linspace(0, 4, n)[::-1] * unit)]
    tbl = Table(names=["x", "y", "ref", "weight"],
                data=[[5,  0, -5,  0]*u.arcsec,
                      [5, -10, 5,  0] * u.arcsec,
                      [2,  0,  1,  0],
                      [1,  1,  1,  2]])
    tbl_source = Source(table=tbl, spectra=specs)

    return tbl_source


@pytest.fixture(scope="function")
def image_source():
    n = 100
    unit = u.Unit("ph s-1 m-2 um-1")
    wave = np.linspace(0.5, 2.5, n) * u.um
    specs = [SourceSpectrum(Empirical1D, points=wave,
                            lookup_table=np.linspace(0, 4, n) * unit)]

    im_wcs = wcs.WCS(naxis=2)
    im_wcs.wcs.cdelt = [0.1, 0.1]
    im_wcs.wcs.cunit = [u.arcsec, u.arcsec]
    im_wcs.wcs.crval = [0, 0]
    im_wcs.wcs.crpix = [50, 50]
    im_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    im = np.zeros((101, 101))
    im[0, 100] = 1
    im[100, 0] = 1
    im[50, 50] = 10

    im_hdu = fits.ImageHDU(data=im, header=im_wcs.to_header())
    im_hdu.header["SPEC_REF"] = 0
    im_source = Source(image_hdu=im_hdu, spectra=specs)

    return im_source


@pytest.mark.usefixtures("input_files", "input_hdulist", "input_tables",
                         "input_spectra")
class TestSourceInit:
    def test_initialises_with_nothing(self):
        src = Source()
        assert isinstance(src, Source)

    @pytest.mark.parametrize("ii", [0, 1])
    def test_initialises_with_table_and_2_spectrum(self, ii,
                                                   input_tables,
                                                   input_spectra):
        table = input_tables[ii]
        src = Source(table=table, spectra=input_spectra)
        assert isinstance(src, Source)
        assert isinstance(src.spectra[0], SourceSpectrum)
        assert isinstance(src.fields[0], Table)

    def test_initialises_with_image_and_1_spectrum(self, input_hdulist,
                                                   input_spectra):
        src = Source(image_hdu=input_hdulist[0], spectra=input_spectra)
        assert isinstance(src, Source)
        assert isinstance(src.spectra[0], SourceSpectrum)
        assert isinstance(src.fields[0], fits.PrimaryHDU)

    def test_initialises_with_image_and_0_spectra(self, input_hdulist):
        src = Source(image_hdu=input_hdulist[0])
        assert len(src.spectra) == 0
        assert src.fields[0].header["SPEC_REF"] == ""

    @pytest.mark.parametrize("ii, dtype",
                             [(0, fits.ImageHDU),
                              (1, Table),
                              (2, Table)])
    def test_initialises_with_filename_and_spectrum(self, ii, dtype,
                                                    input_files, input_spectra):
        fname = input_files[ii]
        src = Source(filename=fname, spectra=input_spectra)
        assert isinstance(src, Source)
        assert isinstance(src.spectra[0], SourceSpectrum)
        assert isinstance(src.fields[0], dtype)

    def test_initialised_with_old_style_arrays(self):
        x, y = [0, 1], [0, -1]
        ref, weight = [0, 0], [1, 10]
        lam = np.linspace(0.5, 2.5, 11) * u.um
        spectra = np.ones(11) * PHOTLAM
        src = Source(x=x, y=y, ref=ref, weight=weight, lam=lam, spectra=spectra)
        assert isinstance(src, Source)
        assert isinstance(src.spectra[0], SourceSpectrum)
        assert isinstance(src.fields[0], Table)


@pytest.mark.usefixtures("table_source", "image_source")
class TestSourceAddition:
    def test_ref_column_always_references_correct_spectrum(self, table_source,
                                                           image_source):
        image_source.append(table_source)
        comb_refs = image_source.fields[1]["ref"]
        tbl_refs = table_source.fields[0]["ref"]
        assert np.all(tbl_refs.data + 1 == comb_refs.data)
        assert image_source.fields[0].header["SPEC_REF"] == 0

    def test_same_as_above_but_reversed(self, table_source, image_source):
        new_source = table_source + image_source
        comb_refs = new_source.fields[0]["ref"]
        tbl_refs = table_source.fields[0]["ref"]
        assert np.all(tbl_refs.data == comb_refs.data)
        assert new_source.fields[1].header["SPEC_REF"] == 3

    def test_imagehdu_with_empty_spec_ref_is_handled(self, table_source,
                                                     image_source):
        image_source.fields[0].header["SPEC_REF"] = ""
        new_source = table_source + image_source
        assert new_source.fields[1].header["SPEC_REF"] == ""


@pytest.mark.usefixtures("table_source", "image_source")
class TestSourceImageInRange:
    def test_returns_an_image_plane_object(self, table_source):
        im = table_source.image_in_range(1*u.um, 2*u.um)
        assert isinstance(im, ImagePlane)

    def test_flux_from_table_on_image_is_as_expected(self, table_source):
        ph = table_source.photons_in_range(1*u.um, 2*u.um)
        ref = table_source.fields[0]["ref"]
        weight = table_source.fields[0]["weight"]
        counts = np.sum([ph.value[r] * w for r, w in zip(ref, weight)])

        im = table_source.image_in_range(1*u.um, 2*u.um)
        assert np.isclose(np.sum(im.image), counts)

    def test_flux_from_imagehdu_is_as_expected(self, image_source):
        im = image_source.image_in_range(1*u.um, 2*u.um, 0.1*u.arcsec)
        assert np.isclose(np.sum(im.image), 24)













@pytest.mark.usefixtures("table_source", "image_source")
class TestSourcePhotonsInRange:
    def test_correct_photons_are_returned_for_table_source(self, table_source):
        ph = table_source.photons_in_range(1, 2)
        assert np.all(np.isclose(ph.value, [4., 2., 2.]))

    def test_correct_photons_are_returned_for_image_source(self, image_source):
        ph = image_source.photons_in_range(1, 2)
        assert np.all(np.isclose(ph.value, [2.]))

    def test_correct_photons_are_returned_for_no_spectra(self, image_source):
        image_source.spectra = []
        ph = image_source.photons_in_range(1, 2)
        assert len(ph) == 0

    @pytest.mark.parametrize("area, expected", [(None, 2), (1, 2), (10, 20)])
    def test_photons_increase_with_area(self, area, expected, image_source):
        ph = image_source.photons_in_range(1, 2, area=area)
        assert np.isclose(ph[0].value, expected)

    def test_photons_returned_only_for_indexes(self, table_source):
        ph = table_source.photons_in_range(1, 2, indexes=[0, 2])
        assert len(ph) == 2
        assert np.all(np.isclose(ph.value, [4, 2]))


class TestSourceShift:
    def test_that_it_does_what_it_should(self):
        pass


class TestSourceRotate:
    def test_that_it_does_what_it_should(self):
        pass


@pytest.mark.usefixtures("input_spectra")
class TestPhotonsInRange:
    @pytest.mark.parametrize("ii, n_ph",
                             [(0, 50),
                              (1, 8e12)])
    def test_returns_correct_number_of_photons_for_one_spectrum(self, ii, n_ph,
                                                                input_spectra):
        spec = input_spectra[ii]
        counts = source2_utils.photons_in_range([spec], 1, 2)
        assert np.isclose(counts.value, n_ph, rtol=2e-3)

    def test_returns_ones_for_unity_spectrum(self):
        flux = np.ones(11) * u.Unit("ph s-1 m-2 um-1")
        wave = np.linspace(1, 2, 11) * u.um
        spec = SourceSpectrum(Empirical1D, points=wave, lookup_table=flux)
        counts = source2_utils.photons_in_range([spec], 1 * u.um, 2 * u.um)
        assert np.isclose(counts.value, 1)

    @pytest.mark.parametrize("area, expected_units",
                             [(1*u.m**2, u.ph / u.s),
                              (None, u.ph / u.s / u.m**2)])
    def test_returns_correct_units_with_without_area_argument(self, area,
                                                              expected_units):
        flux = np.ones(11) * u.Unit("ph s-1 m-2 um-1")
        wave = np.linspace(1, 2, 11) * u.um
        spec = SourceSpectrum(Empirical1D, points=wave, lookup_table=flux)
        counts = source2_utils.photons_in_range([spec], 1 * u.um, 2 * u.um,
                                                area=area)
        assert counts.unit == expected_units

    def test_returns_correct_half_flux_with_bandpass(self):
        flux = np.ones(11) * u.Unit("ph s-1 m-2 um-1")
        wave = np.linspace(0.5, 2.5, 11) * u.um
        spec = SourceSpectrum(Empirical1D, points=wave, lookup_table=flux)
        bandpass = SpectralElement(Empirical1D,
                                   points=np.linspace(1, 2, 13)*u.um,
                                   lookup_table=0.5 * np.ones(13))
        counts = source2_utils.photons_in_range([spec], 1*u.um, 2*u.um,
                                                bandpass=bandpass)
        assert np.isclose(counts.value, 0.5)

    @pytest.mark.parametrize("flux, area, expected",
                             [(np.linspace(0, 1, 11),      1E4*u.cm**2, 0.25),
                              (np.linspace(0, 1, 11)**2,   None, 0.13625),
                              (np.linspace(0, 1, 11)**0.5, 100,  34.931988)])
    def test_with_bandpass_and_area_returns_correct_value(self, flux, area,
                                                          expected):
        flux = flux * u.Unit("ph s-1 m-2 um-1")
        spec = SourceSpectrum(Empirical1D,
                              points=np.linspace(0.5, 2.5, 11) * u.um,
                              lookup_table=flux)
        bandpass = SpectralElement(Empirical1D,
                                   points=np.linspace(1, 2, 13)*u.um,
                                   lookup_table=0.5 * np.ones(13))
        counts = source2_utils.photons_in_range([spec], 1*u.um, 2*u.um,
                                                bandpass=bandpass,
                                                area=area)
        assert np.isclose(counts.value, expected)


class TestMakeImageFromTable:
    def test_returned_object_is_image_hdu(self):
        hdu = source2_utils.make_imagehdu_from_table(x=[0], y=[0], flux=[1])
        assert isinstance(hdu, fits.ImageHDU)

    def test_imagehdu_has_wcs(self):
        hdu = source2_utils.make_imagehdu_from_table(x=[0], y=[0], flux=[1])
        wcs_keys = ["CRPIX1", "CRVAL1", "CDELT1", "CUNIT1"]
        assert np.all([key in hdu.header.keys() for key in wcs_keys])

    def test_stars_are_at_correct_position_for_no_subpixel_accuracy(self):
        # weird behaviour for exactly integer coords e.g. (0, 0)
        x = np.linspace(-1.0001, 1.0001, 9)*u.arcsec
        y = np.linspace(-1.0001, 1.0001, 9)*u.arcsec
        flux = np.ones(len(x))
        hdu = source2_utils.make_imagehdu_from_table(x=x, y=y, flux=flux,
                                                                    pix_scale=0.25*u.arcsec)
        the_wcs = wcs.WCS(hdu)
        yy, xx = the_wcs.wcs_world2pix(y.to(u.deg), x.to(u.deg), 1)
        xx = np.floor(xx).astype(int)
        yy = np.floor(yy).astype(int)
        assert np.all(hdu.data[xx, yy])

    @pytest.mark.parametrize("ii", np.arange(20))
    def test_wcs_returns_correct_pixel_values_for_random_coords(self, ii):
        x = np.random.random(11)*u.arcsec
        y = np.random.random(11)*u.arcsec
        flux = np.ones(len(x))
        hdu = source2_utils.make_imagehdu_from_table(x=x, y=y, flux=flux,
                                                                    pix_scale=0.1*u.arcsec)
        the_wcs = wcs.WCS(hdu)
        yy, xx = the_wcs.wcs_world2pix(y.to(u.deg), x.to(u.deg), 1)
        xx = xx.astype(int)
        yy = yy.astype(int)
        assert np.all(hdu.data[xx, yy])

        # When plotting the image vs the scatter plot
        # The dots match up with a 0.5 px shift, When we intruduce the shift to
        # the test, the dots are on top of the image, but the test fails
        # when using
        # the_wcs.wcs.crpix = [0.5, 0.5]
        # Returning to normal the test passes when (albeit with an image offset)
        # the_wcs.wcs.crpix = [0., 0.]
        #
        # print(hdu.data, flush=True)
        # print(x, y, flush=True)
        # import matplotlib.pyplot as plt
        # plt.subplot(projection=the_wcs)
        # plt.scatter(y*10, x*10)
        # plt.scatter(yy , xx)
        # plt.imshow(hdu.data)
        # plt.show()


class TestScaleImageHDU():
    def test_scaling_properly(self):
        #source2_utils.scale_imagehdu()
        pass




