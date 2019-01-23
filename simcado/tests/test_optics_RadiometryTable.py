# 1 read in the tables
# 2 read in curves from the set of unique files
# 3 create a dictionary of curves
#
import pytest
import os
import inspect

import numpy as np
from astropy.table import Table
from astropy.io import ascii as ioascii

from synphot import SpectralElement, SourceSpectrum

from simcado.optics import radiometry as opt_rad
from simcado.optics import surface as opt_surf
import simcado as sim
from simcado import utils


def mock_dir():
    cur_dirname = os.path.dirname(inspect.getfile(inspect.currentframe()))
    rel_dirname = "mocks/MICADO_SCAO_WIDE/"
    return os.path.abspath(os.path.join(cur_dirname, rel_dirname))


MOCK_DIR = mock_dir()
sim.rc.__search_path__.insert(0, MOCK_DIR)


@pytest.fixture(scope="module")
def input_tables():
    filenames = ["EC_mirrors_ELT.tbl",
                 "EC_mirrors_SCAO_relay.tbl",
                 "EC_mirrors_MICADO_Wide.tbl"]

    return [os.path.join(MOCK_DIR, fname) for fname in filenames]


@pytest.mark.usefixtures("input_tables")
class TestInit:
    def test_initialises_with_no_input(self):
        rt = opt_rad.RadiometryTable()
        assert isinstance(rt, opt_rad.RadiometryTable)
        assert rt.table is None

    def test_initialises_with_single_table(self, input_tables):
        rt = opt_rad.RadiometryTable([input_tables[0]])
        assert isinstance(rt, opt_rad.RadiometryTable)
        assert len(rt.table) == 5

    def test_initialises_with_list_of_tables(self, input_tables):
        rt = opt_rad.RadiometryTable(input_tables)
        assert isinstance(rt, opt_rad.RadiometryTable)
        assert len(rt.table) == 19


@pytest.mark.usefixtures("input_tables")
class TestAddSurfaceList:
    def test_append_single_table_from_filename(self, input_tables):
        rad_table = opt_rad.RadiometryTable()
        rad_table.add_surface_list(input_tables[0])
        assert len(rad_table.table) == 5

    def test_combine_two_tables_from_filename(self, input_tables):
        rad_table = opt_rad.RadiometryTable()
        rad_table.add_surface_list([input_tables[0], input_tables[1]])
        assert len(rad_table.table) == 6

    def test_combine_list_of_filename(self, input_tables):
        rad_table = opt_rad.RadiometryTable()
        rad_table.add_surface_list(input_tables)
        assert len(rad_table.table) == 19


@pytest.mark.usefixtures("input_tables")
class TestCombineTables:
    def test_adds_two_tables(self):
        tblA = Table(names=["colA", "colB"], data=[[0, 1], [0, 1]])
        tblB = Table(names=["colA", "colB"], data=[[2, 3], [2, 3]])
        tblC = opt_rad.combine_tables(tblB, tblA)
        assert np.all(tblC["colB"] == np.array([0, 1, 2, 3]))

    def test_adds_single_table(self):
        tblA = Table(names=["colA", "colB"], data=[[0, 1], [0, 1]])
        tblC = opt_rad.combine_tables(tblA)
        assert np.all(tblC["colA"] == np.array([0, 1]))

    def test_adds_three_tables_to_old_table(self):
        tblA = Table(names=["colA", "colB"], data=[[0, 1], [0, 1]])
        tblB = Table(names=["colA", "colB"], data=[[2, 3], [2, 3]])
        tblC = Table(names=["colA", "colB"], data=[[4, 5], [4, 5]])
        tblD = Table(names=["colA", "colB"], data=[[6, 7], [6, 7]])
        tblE = opt_rad.combine_tables([tblB, tblC, tblD], tblA)
        assert np.all(tblE["colA"] == np.arange(8))

    def test_adds_table_from_filename_to_nothing(self, input_tables):
        tblA = ioascii.read(input_tables[0])
        tblC = opt_rad.combine_tables(tblA)
        assert len(tblC) == 5

    def test_adds_table_from_filename_to_table_object(self, input_tables):
        tblA = ioascii.read(input_tables[0])
        tblB = input_tables[1]
        tblC = opt_rad.combine_tables(tblB, tblA)
        assert len(tblC) == 6

    def test_adds_table_from_filename_to_table_from_file(self, input_tables):
        tblA = input_tables[0]
        tblB = input_tables[1]
        tblC = opt_rad.combine_tables(tblB, tblA)
        assert len(tblC) == 6

    def test_adds_3_tables_from_filename_to_nothing(self, input_tables):
        tblC = opt_rad.combine_tables(input_tables)
        assert len(tblC) == 19

    def test_prepend_table(self):
        tblA = Table(names=["colA", "colB"], data=[[0, 1], [0, 1]])
        tblB = Table(names=["colA", "colB"], data=[[2, 3], [2, 3]])
        tblC = opt_rad.combine_tables(tblB, tblA, prepend=True)
        assert np.all(tblC["colB"] == np.array([2, 3, 0, 1]))


@pytest.mark.usefixtures("input_tables")
class TestMakeSurfaceFromRow:
    def test_return_none_from_empty_row(self, input_tables):
        tblA = ioascii.read(input_tables[0])
        surf = opt_rad.make_surface_from_row(tblA[0])
        assert isinstance(surf, opt_surf.SpectralSurface)

    def test_surface_has_processed_ter_filename_in_row(self, input_tables):
        tblA = ioascii.read(input_tables[0])
        surf = opt_rad.make_surface_from_row(tblA[0])
        assert isinstance(surf.transmission, SpectralElement)
        assert isinstance(surf.reflection, SpectralElement)
        assert isinstance(surf.emissivity, SpectralElement)
        assert isinstance(surf.emission, SourceSpectrum)


class TestRealColname:
    @pytest.mark.parametrize("name, colnames", [
                             ("yahoo", ["Yahoo", "Bogus"]),
                             ("yahoo", ["yahoo", "Bogus"]),
                             ("yahoo", ["YAHOO", "Bogus"])])
    def test_returns_real_name(self, name, colnames):
        assert opt_rad.real_colname(name, colnames) == colnames[0]

    def test_returns_none_if_name_not_in_colname(self):
        assert opt_rad.real_colname("yahoo", ["Bogus"]) is None


@pytest.mark.usefixtures("input_tables")
class TestMakeSurfaceDictFromTable:
    def test_return_dict_from_table(self, input_tables):
        tbl = ioascii.read(input_tables[0])
        surf_dict = opt_rad.make_surface_dict_from_table(tbl)
        assert isinstance(surf_dict, dict)
        assert "M1" in surf_dict


class TestInsertIntoOrderedDict:
    @pytest.mark.parametrize("dic, new_entry, pos",
                             [({}, ["a", 1], 0),
                              ({"x": 42, "y": 3.14}, {"a": 1}, 0),
                              ({"x": 42, "y": 3.14}, {"a": 1, "b": 2}, 1),
                              ({"x": 42, "y": 3.14}, ("a", 1), 2),
                              ({"x": 42, "y": 3.14}, [("b", 2), ("a", 1)], -1)])
    def test_works_as_prescribed(self, dic, new_entry, pos):
        new_dic = opt_rad.insert_into_ordereddict(dic, new_entry, pos)
        print(new_dic)
        assert list(new_dic.keys())[pos] == "a"
        assert list(new_dic.values())[pos] == 1
        assert new_dic["a"] == 1
        if "x" in new_dic:
            assert new_dic["x"] == 42
        if "b" in new_dic:
            assert new_dic["b"] == 2


class TestEmptyType:
    @pytest.mark.parametrize("x, expected",
                             [(int, 0), (float, 0.), (bool, False), (str, "")])
    def test_works_for_all_common_types(self, x, expected):
        assert opt_rad.empty_type(x) == expected


@pytest.mark.usefixtures("input_tables")
class TestAddSurfaceToTable:
    @pytest.mark.parametrize("position", [0, 2, 5])
    def test_(self, input_tables, position):
        tbl = ioascii.read(input_tables[0])
        surf = opt_surf.SpectralSurface(tbl[0]["Filename"])
        tbl = opt_rad.add_surface_to_table(tbl, surf, "new_row", position)
        assert tbl[position]["Filename"] == surf.meta["filename"]
        assert tbl[position]["Name"] == "new_row"









