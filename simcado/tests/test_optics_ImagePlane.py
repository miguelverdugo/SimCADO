import pytest
from pytest import approx
from copy import deepcopy

import numpy as np
from astropy import wcs
from astropy.io import fits
from astropy import units as u
from astropy.table import Table

import simcado.optics.image_plane2 as opt_imp
import simcado.optics.image_plane_utils as impl_utils

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm


PLOTS = False


@pytest.fixture(scope="function")
def image_hdu_square():
    width = 100
    the_wcs = wcs.WCS(naxis=2)
    the_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    the_wcs.wcs.cunit = ["arcsec", "arcsec"]
    the_wcs.wcs.cdelt = [1, 1]
    the_wcs.wcs.crval = [0, 0]
    the_wcs.wcs.crpix = [width // 2, width // 2]

    # theta = 24
    # ca, sa = np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))
    # the_wcs.wcs.pc = np.array([[ca, sa], [-sa, ca]])

    image = np.zeros((width, width))
    hdu = fits.ImageHDU(data=image, header=the_wcs.to_header())

    return hdu


@pytest.fixture(scope="function")
def image_hdu_rect():
    width = 50
    height = 200
    angle = 75
    ca, sa = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    the_wcs = wcs.WCS(naxis=2)
    the_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    the_wcs.wcs.cunit = ["arcsec", "arcsec"]
    the_wcs.wcs.cdelt = [1, 1]
    the_wcs.wcs.crval = [0, 0]
    the_wcs.wcs.crpix = [width // 2, height // 2]
    the_wcs.wcs.pc = [[ca, sa], [-sa, ca]]

    image = np.random.random(size=(height, width))
    hdu = fits.ImageHDU(data=image, header=the_wcs.to_header())

    return hdu


@pytest.fixture(scope="function")
def input_table():
    x = [-10, -10, 0, 10, 10] * u.arcsec
    y = [-10, 10, 0, -10, 10] * u.arcsec
    f = [1, 3, 1, 1, 5]
    tbl = Table(names=["x", "y", "flux"], data=[x, y, f])

    return tbl


@pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
class TestCombineTableBoundaries:
    def test_all_three_tables_are_inside_header_wcs(self, input_table):
        tbl1 = deepcopy(input_table)
        tbl2 = deepcopy(input_table)
        tbl3 = deepcopy(input_table)

        tbl2["x"] -= 25
        tbl3["y"] -= 60

        hdr = opt_imp._make_bounding_header_for_tables([tbl1, tbl2, tbl3])

        for tbl in [tbl1, tbl2, tbl3]:
            x, y = opt_imp.sky2pix(hdr, tbl["x"] / 3600., tbl["y"] / 3600.)
            for xi, yi in zip(x,y):
                assert xi >= 0 and xi < hdr["NAXIS1"]
                assert yi >= 0 and yi < hdr["NAXIS2"]


        if PLOTS:
            x, y = opt_imp.calc_footprint(hdr)
            x, y = opt_imp.sky2pix(hdr, x, y)
            x0, y0 = opt_imp.sky2pix(hdr, 0, 0)

            plt.plot(x, y, "b")
            plt.plot(x0, y0, "ro")
            for tbl in [tbl1, tbl2, tbl3]:
                x, y = opt_imp.sky2pix(hdr, tbl["x"] / 3600., tbl["y"] / 3600.)
                plt.plot(x, y, "k.")

            plt.show()


@pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
class TestCombineImageHDUBoundaries:
    def test_all_two_imagehdus_are_inside_header_wcs(self, image_hdu_square,
                                                     image_hdu_rect):

        image_hdu_rect.header["CRVAL1"] -= 0 * u.arcsec.to(u.deg)
        image_hdu_square.header["CRVAL2"] += 0 * u.arcsec.to(u.deg)

        hdr = opt_imp._make_bounding_header_from_imagehdus([image_hdu_square,
                                                            image_hdu_rect])
        w = wcs.WCS(hdr)
        for im in [image_hdu_square, image_hdu_rect]:
            im_wcs = wcs.WCS(im)
            x, y = im_wcs.calc_footprint().T
            x, y = w.wcs_world2pix(x, y, 1)
            for xi, yi in zip(x, y):
                assert xi >= 0 and xi < hdr["NAXIS1"]
                assert yi >= 0 and yi < hdr["NAXIS2"]


        if PLOTS:
            for im in [image_hdu_square, image_hdu_rect]:
                im_wcs = wcs.WCS(im)
                x, y = im_wcs.calc_footprint().T
                x, y = w.wcs_world2pix(x, y, 1)
                plt.plot(x, y, "r-")

            x, y = w.calc_footprint(center=False).T
            x, y = w.wcs_world2pix(x, y, 1)
            x0, y0 = w.wcs_world2pix(0, 0, 1)

            plt.plot(x, y, "b")
            plt.plot(x0, y0, "ro")
            plt.gca().set_aspect(1)
            plt.show()


@pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
class TestGetCanvasHeader:
    def test_all_5_objects_are_inside_header_wcs(self, image_hdu_square,
                                                 image_hdu_rect, input_table):

        tbl1 = deepcopy(input_table)
        tbl2 = deepcopy(input_table)
        tbl3 = deepcopy(input_table)

        tbl2["x"] -= 150
        tbl3["y"] -= 100

        image_hdu_rect.header["CRVAL1"] += 100 * u.arcsec.to(u.deg)
        image_hdu_square.header["CRVAL1"] += 0 * u.arcsec.to(u.deg)
        image_hdu_square.header["CRVAL2"] += 100 * u.arcsec.to(u.deg)

        hdr = opt_imp.get_canvas_header([image_hdu_square, tbl1, tbl2, tbl3,
                                         image_hdu_rect])

        w = wcs.WCS(hdr)
        for im in [image_hdu_square, image_hdu_rect]:
            im_wcs = wcs.WCS(im)
            x, y = im_wcs.calc_footprint().T
            x, y = w.wcs_world2pix(x, y, 1)
            for xi, yi in zip(x, y):
                assert xi >= -1e-4 and xi < hdr["NAXIS1"]
                assert yi >= -1e-4 and yi < hdr["NAXIS2"]

        for tbl in [tbl1, tbl2, tbl3]:
            x, y = w.wcs_world2pix(tbl["x"] / 3600., tbl["y"] / 3600., 1)
            for xi, yi in zip(x, y):
                assert xi >= -1e-4 and xi < hdr["NAXIS1"]
                assert yi >= -1e-4 and yi < hdr["NAXIS2"]


        if PLOTS:

            x, y = w.calc_footprint(center=False).T
            x, y = w.wcs_world2pix(x, y, 1)
            x0, y0 = w.wcs_world2pix(0, 0, 1)
            plt.plot(x, y, "b")
            plt.plot(x0, y0, "ro")

            for tbl in [tbl1, tbl2, tbl3]:
                x, y = w.wcs_world2pix(tbl["x"] / 3600., tbl["y"] / 3600., 1)
                plt.plot(x, y, "k.")

            for im in [image_hdu_square, image_hdu_rect]:
                im_wcs = wcs.WCS(im)
                x, y = im_wcs.calc_footprint().T
                x, y = w.wcs_world2pix(x, y, 1)
                plt.plot(x, y, "r-")

            plt.gca().set_aspect(1)
            plt.show()


@pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
class TestAddTableToImageHDU:
    def test_points_are_added_to_small_canvas(self, input_table, ):
        tbl1 = deepcopy(input_table)
        hdr = opt_imp.get_canvas_header([tbl1])

        im = np.zeros((hdr["NAXIS2"], hdr["NAXIS1"]))
        canvas_hdu = fits.ImageHDU(header=hdr, data=im)
        canvas_hdu = opt_imp.add_table_to_imagehdu(tbl1, canvas_hdu)

        if PLOTS:
            "top left is green, top right is yellow"
            plt.imshow(canvas_hdu.data.T, origin="lower")
            plt.show()

    # add a paramaterised test here to check border cases
    def test_points_are_added_to_massive_canvas(self, input_table):
        tbl1 = deepcopy(input_table)
        tbl2 = deepcopy(input_table)
        tbl3 = deepcopy(input_table)

        tbl1["y"] += 50
        tbl2["x"] += 20
        tbl3["x"] -= 25
        tbl3["y"] -= 25

        hdr = opt_imp.get_canvas_header([tbl1, tbl2, tbl3],
                                        pixel_scale=1*u.arcsec)
        im = np.zeros((hdr["NAXIS1"], hdr["NAXIS2"]))
        canvas_hdu = fits.ImageHDU(header=hdr, data=im)

        for tbl in [tbl1, tbl2, tbl3]:
            canvas_hdu = opt_imp.add_table_to_imagehdu(tbl, canvas_hdu, True)

        total_flux = np.sum([tbl1["flux"], tbl1["flux"], tbl1["flux"]])
        assert np.sum(canvas_hdu.data) == total_flux

        if PLOTS:
            w = wcs.WCS(hdr)
            x, y = w.wcs_world2pix(0, 0, 1)
            plt.plot(x, y, "ro")
            "top left is green, top right is yellow"
            plt.imshow(canvas_hdu.data.T, origin="lower")
            plt.show()


@pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
class TestAddImageHDUToImageHDU:
    def test_image_is_added_to_small_canvas(self, image_hdu_rect,
                                            image_hdu_square):
        im_hdu = image_hdu_rect
        im_hdu.header["CRVAL1"] -= 150*u.arcsec.to(u.deg)
        im_hdu.header["CRVAL2"] += 20*u.arcsec.to(u.deg)
        hdr = opt_imp.get_canvas_header([im_hdu, image_hdu_square])

        im = np.zeros((hdr["NAXIS1"], hdr["NAXIS2"]))
        canvas_hdu = fits.ImageHDU(header=hdr, data=im)
        canvas_hdu = opt_imp.add_imagehdu_to_imagehdu(im_hdu, canvas_hdu)

        if PLOTS:
            for im in [im_hdu, image_hdu_square]:
                x, y = opt_imp.calc_footprint(im.header)
                x, y = opt_imp.sky2pix(canvas_hdu.header, x, y)
                plt.plot(x, y, "r-")

            x0, y0 = opt_imp.sky2pix(canvas_hdu.header, 0, 0)
            plt.plot(x0, y0, "ro")
            plt.gca().set_aspect(1)

            plt.imshow(canvas_hdu.data.T, origin="lower")

            plt.show()

    def test_image_and_tables_on_large_canvas(self, input_table, image_hdu_rect,
                                              image_hdu_square):
        tbl1 = deepcopy(input_table)
        tbl2 = deepcopy(input_table)

        tbl1["y"] -= 100
        tbl2["x"] += 100
        tbl2["y"] += 100

        im_hdu = image_hdu_rect
        im_hdu.header["CRVAL1"] -= 150*u.arcsec.to(u.deg)
        im_hdu.header["CRVAL2"] += 20*u.arcsec.to(u.deg)

        hdr = opt_imp.get_canvas_header([im_hdu, image_hdu_square, tbl1, tbl2],
                                        pixel_scale=5*u.arcsec)
        im = np.zeros((hdr["NAXIS1"], hdr["NAXIS2"]))
        canvas_hdu = fits.ImageHDU(header=hdr, data=im)

        canvas_hdu = opt_imp.add_table_to_imagehdu(tbl1, canvas_hdu)
        canvas_hdu = opt_imp.add_table_to_imagehdu(tbl2, canvas_hdu)
        canvas_hdu = opt_imp.add_imagehdu_to_imagehdu(im_hdu, canvas_hdu)
        canvas_hdu = opt_imp.add_imagehdu_to_imagehdu(image_hdu_square,
                                                      canvas_hdu)

        if PLOTS:

            w = wcs.WCS(canvas_hdu.header)
            for im in [im_hdu, image_hdu_square]:
                im_wcs = wcs.WCS(im)
                x, y = im_wcs.calc_footprint().T
                x, y = w.wcs_world2pix(x, y, 1)
                plt.plot(x, y, "r-")

            x0, y0 = w.wcs_world2pix(0, 0, 1)
            plt.plot(x0, y0, "ro")
            plt.gca().set_aspect(1)

            plt.imshow(canvas_hdu.data.T, origin="lower")

            plt.show()


class TestImagePlaneAdd:
    def test_add_many_tables_etc(self, input_table, image_hdu_rect,
                                 image_hdu_square):
        tbl1 = deepcopy(input_table)
        tbl2 = deepcopy(input_table)

        tbl1["y"] -= 50
        tbl2["x"] += 50
        tbl2["y"] += 50

        im_hdu = image_hdu_rect
        im_hdu.header["CRVAL1"] -= 150*u.arcsec.to(u.deg)
        im_hdu.header["CRVAL2"] += 20*u.arcsec.to(u.deg)

        fields = [im_hdu, tbl1, tbl2, image_hdu_square]
        hdr = opt_imp.get_canvas_header(fields, pixel_scale=1*u.arcsec)
        implane = opt_imp.ImagePlane(hdr)
        implane.add(fields)

        if PLOTS:
            for im in [im_hdu, image_hdu_square]:
                x, y = opt_imp.calc_footprint(im.header)
                x, y = opt_imp.sky2pix(implane.header, x, y)
                plt.plot(x, y, "r-")

            for tbl in [tbl1, tbl2]:
                hdr = opt_imp._make_bounding_header_for_tables([tbl])
                x, y = opt_imp.calc_footprint(hdr)
                x, y = opt_imp.sky2pix(implane.header, x, y)
                plt.plot(x, y, "r-")

            x0, y0 = opt_imp.sky2pix(implane.header, 0, 0)
            plt.plot(x0, y0, "ro")
            plt.gca().set_aspect(1)

            plt.imshow(implane.data.T, origin="lower")

            plt.show()


###############################################################################
# ..todo: When you have time, reintegrate these tests, There are some good ones


# import pytest
# from pytest import approx
# from copy import deepcopy
#
# import numpy as np
# from astropy import wcs
# from astropy.io import fits
# from astropy import units as u
# from astropy.table import Table
#
# import simcado.optics.image_plane as opt_imp
# import simcado.optics.image_plane_utils as impl_utils
#
# import matplotlib.pyplot as plt
# from matplotlib.colors import LogNorm
#
#
# @pytest.fixture(scope="function")
# def image_hdu_square():
#     width = 100
#     the_wcs = wcs.WCS(naxis=2)
#     the_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
#     the_wcs.wcs.cunit = ["arcsec", "arcsec"]
#     the_wcs.wcs.cdelt = [1, 1]
#     the_wcs.wcs.crval = [0, 0]
#     the_wcs.wcs.crpix = [width // 2, width // 2]
#
#     # theta = 24
#     # ca, sa = np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))
#     # the_wcs.wcs.pc = np.array([[ca, sa], [-sa, ca]])
#
#     image = np.zeros((width, width))
#     hdu = fits.ImageHDU(data=image, header=the_wcs.to_header())
#
#     return hdu
#
#
# @pytest.fixture(scope="function")
# def image_hdu_rect():
#     width = 50
#     height = 200
#     the_wcs = wcs.WCS(naxis=2)
#     the_wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
#     the_wcs.wcs.cunit = ["arcsec", "arcsec"]
#     the_wcs.wcs.cdelt = [1, 1]
#     the_wcs.wcs.crval = [0, 0]
#     the_wcs.wcs.crpix = [width // 2, height // 2]
#
#     image = np.random.random(size=(height, width))
#     hdu = fits.ImageHDU(data=image, header=the_wcs.to_header())
#
#     return hdu
#
#
# @pytest.fixture(scope="function")
# def input_table():
#     x = [-10, -10, 0, 10, 10] * u.arcsec
#     y = [-10, 10, 0, -10, 10] * u.arcsec
#     tbl = Table(names=["x", "y"], data=[x, y])
#
#     return tbl
#
#
# @pytest.mark.usefixtures("image_hdu_square")
# class TestGetSpatialExtentOfHeader:
#     def test_returns_right_sky_coords_from_known_coords(self, image_hdu_square):
#         xsky, ysky = impl_utils.get_corner_sky_coords_from_header(image_hdu_square.header)
#         xsky = np.array(xsky)
#         xsky[xsky > 180 ] -= 360
#         xsky = np.array(xsky)*u.deg.to(u.arcsec)
#         ysky = np.array(ysky)*u.deg.to(u.arcsec)
#         dx = max(xsky) - min(xsky)
#         dy = max(ysky) - min(ysky)
#         assert dx == approx(image_hdu_square.header["NAXIS1"])
#         assert dy == approx(image_hdu_square.header["NAXIS2"])
#
#
# @pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect", "input_table")
# class TestMakeImagePlaneHeader:
#     def test_header_contains_future_naxis_pixel_sizes(self, image_hdu_square,
#                                                       image_hdu_rect):
#         hdr = impl_utils.make_image_plane_header([image_hdu_square,
#                                                   image_hdu_rect])
#         assert hdr["NAXIS1"] == 100 + 2
#         assert hdr["NAXIS2"] == 200 + 2
#
#     @pytest.mark.parametrize("offset", -np.random.randint(200, 1001, 10))
#     def test_header_contains_spread_out_regions(self, offset, image_hdu_square,
#                                                 image_hdu_rect):
#         image_hdu_rect.header["CRVAL1"] += offset*u.arcsec.to(u.deg)
#         hdr = impl_utils.make_image_plane_header([image_hdu_square,
#                                                   image_hdu_rect])
#         image_width = image_hdu_square.header["NAXIS1"] // 2 + \
#                       image_hdu_rect.header["NAXIS1"] // 2 + abs(offset) + 2
#
#         assert hdr["NAXIS1"] == image_width
#
#     @pytest.mark.parametrize("offset", [0, 10, 25, 50])
#     def test_header_has_correct_size_based_on_table_extremes(self, offset,
#                                                              input_table):
#         tbl1 = input_table
#         tbl2 = deepcopy(input_table)
#         tbl3 = deepcopy(input_table)
#         tbl2["x"] += offset
#         tbl3["y"] += offset
#         hdr = impl_utils.make_image_plane_header([tbl1, tbl2, tbl3],
#                                                  pixel_scale=0.1*u.arcsec)
#
#         assert hdr["NAXIS1"] == np.max(tbl1["x"] + tbl2["x"]) * 10 + 2
#         assert hdr["NAXIS2"] == np.max(tbl1["y"] + tbl3["y"]) * 10 + 2
#
#     @pytest.mark.parametrize("pix_scl", [5, 1, 0.5, 0.1])
#     def test_header_has_correct_size_with_tbl_and_image_input(self, input_table,
#                                                               image_hdu_square,
#                                                               pix_scl):
#         input_table["x"] += 100
#         hdr = impl_utils.make_image_plane_header([image_hdu_square,
#                                                   input_table],
#                                                  pixel_scale=pix_scl * u.arcsec)
#         assert hdr["NAXIS1"] == approx(hdr["CRPIX1"] +
#                                        np.max(input_table["x"]) / pix_scl + 1,
#                                        abs=0.5)
#
#     def test_header_does_not_contain_negative_naxis_keywords(self):
#         pass
#
#
#
#
# class TestGetCornerSkyCoordsFromTable:
#     def test_table_with_column_units_returns_right_values(self):
#         x, y = [1] * u.arcmin, [1] * u.arcmin
#         tbl = Table(names=["x", "y"], data=[x, y])
#         xsky, ysky = impl_utils.get_corner_sky_coords_from_table(tbl)
#
#         assert xsky[0]*u.deg == x[0].to(u.deg)
#         assert ysky[0]*u.deg == y[0].to(u.deg)
#
#     def test_table_with_meta_units_returns_right_values(self):
#         x, y = [1], [1]
#         tbl = Table(names=["x", "y"], data=[x, y])
#         tbl.meta.update({"x_unit": u.arcmin, "y_unit": u.arcmin})
#         xsky, ysky = impl_utils.get_corner_sky_coords_from_table(tbl)
#
#         assert xsky[0] == x[0]*u.arcmin.to(u.deg)
#         assert ysky[0] == y[0]*u.arcmin.to(u.deg)
#
#     def test_table_with_default_units_returns_right_values(self):
#         x, y = [60], [60]      # because default unit is arcsec
#         tbl = Table(names=["x", "y"], data=[x, y])
#         xsky, ysky = impl_utils.get_corner_sky_coords_from_table(tbl)
#
#         assert pytest.approx(xsky[0] == x[0] * u.arcmin.to(u.deg))
#         assert pytest.approx(ysky[0] == y[0] * u.arcmin.to(u.deg))
#
#
# @pytest.mark.usefixtures("image_hdu_square")
# class TestGetCornerSkyCoords:
#     def test_returns_coords_for_combination_of_table_and_header(self,
#                                                             image_hdu_square):
#         x, y = [-100, 70] * u.arcsec, [0, 0] * u.arcsec
#         tbl = Table(names=["x", "y"], data=[x, y])
#         xsky, ysky = impl_utils.get_corner_sky_coords([tbl, image_hdu_square])
#
#         assert np.all((xsky == x.to(u.deg).value))
#
#
# @pytest.mark.usefixtures("image_hdu_square")
# class TestAddTableToImageHDU:
#     @pytest.mark.parametrize("xpix, ypix, value",
#                              [(51, 51, 1),
#                               (48, 51, 2),
#                               (48, 48, 3),
#                               (51, 48, 4)])
#     def test_integer_pixel_fluxes_are_added_correctly(self, xpix, ypix, value,
#                                                       image_hdu_square):
#         # Given the weird behaviour on pixel boundaries
#         x, y = [1.5, -1.5, -1.5, 1.5]*u.arcsec, [1.5, 1.5, -1.5, -1.5]*u.arcsec
#         flux = [1, 2, 3, 4] * u.Unit("ph s-1")
#         tbl = Table(names=["x", "y", "flux"], data=[x, y, flux])
#
#         hdu = impl_utils.add_table_to_imagehdu(tbl, image_hdu_square,
#                                                sub_pixel=False)
#         assert hdu.data[xpix, ypix] == value
#
#     @pytest.mark.parametrize("x, y, flux, xpix, ypix, value",
#                              [([0], [0], [1], 50, 50, 1.),
#                               ([0.2], [0.2], [1], 50, 50, 0.64),
#                               ([-0.2], [-0.2], [1], 49, 49, 0.04),
#                               ([5], [-5.2], [1], 55, 45, 0.8),
#                               ([5], [-5.2], [1], 55, 44, 0.2)])
#     def test_sub_pixel_fluxes_are_added_correctly(self, x, y, flux, xpix, ypix,
#                                                   value, image_hdu_square):
#         # Given the weird behaviour on pixel boundaries
#         tbl = Table(names=["x", "y", "flux"],
#                     data=[x*u.arcsec, y*u.arcsec, flux*u.Unit("ph s-1")])
#         hdu = impl_utils.add_table_to_imagehdu(tbl, image_hdu_square,
#                                                sub_pixel=True)
#
#         assert np.isclose(hdu.data[xpix, ypix], value)
#         # import matplotlib.pyplot as plt
#         # plt.imshow(hdu.data[45:55,45:55], origin="lower")
#         # plt.colorbar()
#         # plt.show()
#
#     @pytest.mark.parametrize("x, y, flux",
#                              [([100, -100], [0, 0], [10, 10])])
#     def test_source_outside_canvas_are_ignored(self, x, y, flux,
#                                                image_hdu_square):
#             # Given the weird behaviour on pixel boundaries
#             tbl = Table(names=["x", "y", "flux"],
#                         data=[x * u.arcsec, y * u.arcsec,
#                               flux * u.Unit("ph s-1")])
#             hdu = impl_utils.add_table_to_imagehdu(tbl, image_hdu_square,
#                                                    sub_pixel=True)
#
#             assert np.sum(hdu.data) == 0
#
#
# @pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect")
# class TestAddImagehduToImageHDU:
#     @pytest.mark.parametrize("angle", [0, 30, 45, 89])
#     def test_image_added_conserves_flux(self, angle, image_hdu_square):
#         canvas = deepcopy(image_hdu_square)
#         canvas.data = np.zeros((200, 200))
#         canvas.header["CRPIX1"] *= 2
#         canvas.header["CRPIX2"] *= 2
#
#         angle = np.deg2rad(angle)
#         image_hdu_square.data = np.ones((100, 100))
#         image_hdu_square.header["PC1_1"] = np.cos(angle)
#         image_hdu_square.header["PC1_2"] = np.sin(angle)
#         image_hdu_square.header["PC2_1"] = -np.sin(angle)
#         image_hdu_square.header["PC2_2"] = np.cos(angle)
#
#         canvas = impl_utils.add_imagehdu_to_imagehdu(image_hdu_square, canvas)
#         assert np.isclose(np.sum(canvas.data), np.sum(image_hdu_square.data))
#
#
# class TestSubPixelFractions:
#     @pytest.mark.parametrize("x, y, xx_exp ,yy_exp, ff_exp",
#      [(   0,    0, [ 0, 0,  0, 0], [ 0,  0, 0, 0], [  1.,    0,    0,    0]),
#       ( 0.2,  0.2, [ 0, 1,  0, 1], [ 0,  0, 1, 1], [0.64, 0.16, 0.16, 0.04]),
#       (-0.2, -0.2, [-1, 0, -1, 0], [-1, -1, 0, 0], [0.04, 0.16, 0.16, 0.64]),
#       ( 0.2, -0.2, [ 0, 1,  0, 1], [-1, -1, 0, 0], [0.16, 0.04, 0.64, 0.16])])
#     def test_fractions_come_out_correctly_for_mixed_offsets(self, x, y, xx_exp,
#                                                             yy_exp, ff_exp):
#         xx, yy, ff = impl_utils.sub_pixel_fractions(x, y)
#         assert pytest.approx(xx == xx_exp)
#         assert pytest.approx(yy == yy_exp)
#         assert pytest.approx(ff == ff_exp)
#
#
# @pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect")
# class TestImagePlaneInit:
#     def test_throws_error_when_initialised_with_nothing(self):
#         with pytest.raises(TypeError):
#             opt_imp.ImagePlane()
#
#     def test_initialises_with_header_with_hdu(self, image_hdu_square,
#                                               image_hdu_rect):
#         hdr = impl_utils.make_image_plane_header(pixel_scale=0.1 * u.arcsec,
#                                                  hdu_or_table_list=[image_hdu_rect,
#                                                  image_hdu_square])
#         implane = opt_imp.ImagePlane(hdr)
#         assert isinstance(implane, opt_imp.ImagePlane)
#         assert isinstance(implane.hdu, fits.ImageHDU)
#
#     def test_throws_error_if_header_does_not_have_valid_wcs(self):
#         with pytest.raises(ValueError):
#             opt_imp.ImagePlane(fits.Header())
#
#
# @pytest.mark.usefixtures("image_hdu_square", "image_hdu_rect")
# class TestImagePlaneAdd:
#     def test_simple_add_imagehdu_conserves_flux(self, image_hdu_square,
#                                                 image_hdu_rect):
#         fields = [image_hdu_rect, image_hdu_square]
#         hdr = impl_utils.make_image_plane_header(pixel_scale=1 * u.arcsec,
#                                                  hdu_or_table_list=fields)
#
#         print(wcs.WCS(image_hdu_rect))
#         print(wcs.WCS(hdr))
#
#         implane = opt_imp.ImagePlane(hdr)
#         implane.add(image_hdu_rect)
#
#         plt.imshow(image_hdu_rect.data.T)
#         x, y = wcs.WCS(image_hdu_rect).wcs_world2pix(0, 0, 1)
#         print(x, y)
#         plt.plot(x, y, "ro")
#         plt.show()
#
#         plt.imshow(implane.data.T)
#         x, y = wcs.WCS(image_hdu_rect).wcs_world2pix(0, 0, 1)
#         print(x, y)
#         plt.plot(x, y, "ro")
#         plt.show()
#
#         assert np.sum(implane.data) == approx(np.sum(image_hdu_rect.data))
#
#     def test_simple_add_table_conserves_flux(self, image_hdu_rect):
#         x = [75, -75]*u.arcsec
#         y = [0, 0]*u.arcsec
#         flux = [30, 20] * u.Unit("ph s-1")
#         tbl = Table(names=["x", "y", "flux"], data=[x, y, flux])
#
#         hdr = impl_utils.make_image_plane_header(pixel_scale=0.1 * u.arcsec,
#                                                  hdu_or_table_list=[image_hdu_rect,
#                                                  tbl])
#         implane = opt_imp.ImagePlane(hdr)
#         implane.add(tbl)
#         assert np.isclose(np.sum(implane.data), np.sum(flux.value))
#
#     def test_compound_add_image_and_table_conserves_flux(self, image_hdu_rect):
#         x = [75, -75]*u.arcsec
#         y = [0, 0]*u.arcsec
#         flux = [30, 20] * u.Unit("ph s-1")
#         tbl = Table(names=["x", "y", "flux"], data=[x, y, flux])
#
#         hdr = impl_utils.make_image_plane_header(pixel_scale=0.1 * u.arcsec,
#                                                  hdu_or_table_list=[image_hdu_rect,
#                                                                     tbl])
#         implane = opt_imp.ImagePlane(hdr)
#         implane.add(tbl)
#         implane.add(image_hdu_rect)
#         assert np.isclose(np.sum(implane.data),
#                           np.sum(flux.value) + np.sum(image_hdu_rect.data))
