from __future__ import annotations

########################################################################################################################
__doc__ = \
    """
The main class here is ``_RDKitPrepMixin``, which adds the various pre checks.
It does not rely on any ``Params`` entry stuff. So can be used by itself for testing.

    """

__author__ = "Matteo Ferla. [Github](https://github.com/matteoferla)"
__email__ = "matteo.ferla@gmail.com"
__date__ = "2020 A.D."
__license__ = "MIT"
__version__ = "1"
__citation__ = "None."

########################################################################################################################

from typing import List, Dict, Union
from collections import defaultdict, deque, namedtuple
from rdkit import Chem
from rdkit.Chem import AllChem
from warnings import warn
import re
from typing import Optional

class _RDKitPrepMixin:

    def __init__(self):
        # This exists to stop the IDE from getting angry.
        # And for debugging!
        self.NAME = 'LIG'
        self.mol = None
        self.generic = False
        self._rtype = []

    @classmethod
    def from_mol(cls, mol: Chem.Mol, generic:bool=False, name:Optional[str]=None) -> _RDKitPrepMixin:
        self = cls()
        self.mol = mol
        self.generic = generic
        if name is not None:
            self.NAME = name
        self.fix_mol()
        # conversion elsewhere
        return self

    @classmethod
    def add_names(cls, mol: Chem.Mol, names: List[str], name:Optional[str]=None) -> Chem.Mol:
        """
        Quick way to add atom names to a mol object --adds them the normal way.

        :param mol: Chem.Mol, will actually be edited in place.
        :param names: list of unique names.
        :param name: 3letter code for the molecule.
        :return: the mol
        """
        assert len(set(names)) == len(names), 'Atom Names are repeated.'
        if mol.GetNumAtoms() > len(names):
            warn('There are more atoms in mol than were provided.')
        elif mol.GetNumAtoms() < len(names):
            raise ValueError('There are less atoms in mol than were provided.')
        self = cls()
        if name is not None:
            self.NAME = name
        self.mol = mol
        self.fix_mol()
        for name, atom in zip(names, self.mol.GetAtoms()):
            info = atom.GetPDBResidueInfo().SetName(name)
        return self.mol

    def fix_mol(self):
        # partial charges.
        if not self.mol.GetAtomWithIdx(0).HasProp('_GasteigerCharge'):
            self._add_partial_charges()
        self._fix_atom_names()
        if self.generic is True:
            self._add_genrtypes()
        else:
            self._add_rtypes()

    def _add_rtypes(self) -> None:
        """
        Add Rosetta Atom types to each atom.
        Mostly a guess...
        """

        # These are the elements with a single type.
        # Some have oxidation states '2p', but only one...
        element_to_type = {'B': 'Bsp2', 'F': 'F', 'CL': 'Cl', 'BR': 'Br', 'I': 'I', 'ZN': 'Zn2p', 'CO': 'Co2p',
                           'CU': 'Cu2p', 'MG': 'Mg2p', 'CA': 'Ca2p', 'Si': 'Si', 'NA': 'Na1p', 'K': 'K1p', 'HE': 'He',
                           'LI': 'Li', 'BE': 'Be', 'NE': 'Ne', 'AL': 'Al', 'AR': 'Ar', 'SC': 'Sc', 'TI': 'Ti', 'V': 'V',
                           'CR': 'Cr', 'MN': 'Mn', 'NI': 'Ni', 'GA': 'Ga', 'GE': 'Ge', 'AS': 'As', 'SE': 'Se',
                           'KR': 'Kr', 'RB': 'Rb', 'SR': 'Sr', 'Y': 'Y', 'ZR': 'Zr', 'NB': 'Nb', 'MO': 'Mo', 'TC': 'Tc',
                           'RU': 'Ru', 'RH': 'Rh', 'PD': 'Pd', 'AG': 'Ag', 'CD': 'Cd', 'IN': 'In', 'SN': 'Sn',
                           'SB': 'Sb', 'TE': 'Te', 'XE': 'Xe', 'CS': 'Cs', 'BA': 'Ba', 'LA': 'La', 'CE': 'Ce',
                           'PR': 'Pr', 'ND': 'Nd', 'PM': 'Pm', 'SM': 'Sm', 'EU': 'Eu', 'GD': 'Gd', 'TB': 'Tb',
                           'DY': 'Dy', 'HO': 'Ho', 'ER': 'Er', 'TM': 'Tm', 'YB': 'Yb', 'LU': 'Lu', 'HF': 'Hf',
                           'TA': 'Ta', 'W': 'W', 'RE': 'Re', 'OS': 'Os', 'IR': 'Ir', 'PT': 'Pt', 'AU': 'Au', 'HG': 'Hg',
                           'TL': 'Tl', 'PB': 'Pb', 'BI': 'Bi', 'PO': 'Po', 'AT': 'At', 'RN': 'Rn', 'FR': 'Fr',
                           'RA': 'Ra', 'AC': 'Ac', 'TH': 'Th', 'PA': 'Pa', 'U': 'U', 'NP': 'Np', 'PU': 'Pu', 'AM': 'Am',
                           'CM': 'Cm', 'BK': 'Bk', 'CF': 'Cf', 'ES': 'Es', 'FM': 'Fm', 'MD': 'Md', 'NO': 'No',
                           'LR': 'Lr'}

        groups = [
                  {'name': 'silane', 'SMARTS': '[Si]~O', 'types': ['Si', 'OSi']},
                  {'name': 'phosphoric', 'SMARTS': 'P[OH]', 'types': ['Pha', 'OHha', 'Hha']},
                  {'name': 'phosphate', 'SMARTS': 'P~O', 'types': ['Pha', 'OPha']},
                  {'name': 'free carbonic acid?', 'SMARTS': 'C(=O)(O)O', 'types': ['CO3', 'OC3', 'OC3']}, # no idea.
                  {'name': 'carboxylate', 'SMARTS': 'C(=O)[O-]', 'types': ['COO', 'OOC', 'OOC']},
                  {'name': 'carboxylic', 'SMARTS': 'C(=O)[OH]', 'types': ['COO', 'OOC', 'OH']},
                  {'name': 'ester', 'SMARTS': 'C(=O)OC', 'types': ['COO', 'Oet2', 'Oet3', None]},
                  {'name': 'ester?', 'SMARTS': 'C(=O)O', 'types': ['COO', 'OOC', 'OOC']},
                  {'name': '3amide', 'SMARTS': 'C(=O)N(C)C', 'types': ['CNH2', 'ONH2', 'Npro', None, None]},
                  {'name': '3amide', 'SMARTS': 'C(=O)NC', 'types': ['CNH2', 'ONH2', 'Nbb', None]},
                  {'name': 'amide', 'SMARTS': 'C(=O)N', 'types': ['CNH2', 'ONH2', 'NH2O']},
                  {'name': 'keto-aldehyde', 'SMARTS': 'C(=O)', 'types': [None, 'OOC']}, ## ???
                  {'name': '2amine', 'SMARTS': 'CNC', 'types': [None, 'Nbb', None]}, # actually Nbb is a amide.
                  {'name': 'azo', 'SMARTS': 'NN', 'types': ['NtrR', 'NtrR']},
                  {'name': 'azo', 'SMARTS': 'nn', 'types': ['NtrR', 'NtrR']},
                  {'name': 'aramid?', 'SMARTS': 'nc(o)c', 'types': ['NtrR', 'Caro', 'Oaro', None]}, # unsure how it's written
                  {'name': 'nitrile', 'SMARTS': 'C#N', 'types': ['Caro', 'NtrR']}, ## ???
                  {'name': 'imino', 'SMARTS': 'C=N', 'types': [None, 'Nhis']},
                  {'name': 'nitro', 'SMARTS': '[N+](=O)[O-]', 'types': ['Nhis','OOC', 'OOC']},
                  {'name': 'nitro_aro', 'SMARTS': 'n(=o)o', 'types': ['Nhis','OOC', 'OOC']},
                  {'name': 'furan', 'SMARTS': 'coc', 'types': ['aroC', 'Oaro', 'aroC']},
                  {'name': 'ether', 'SMARTS': 'COC', 'types': [None, 'Oet3', None]},
                  {'name': 'hydroxyl', 'SMARTS': '[OH]', 'types': ['OH']},
                  {'name': 'guanidium', 'SMARTS': 'NC(=N)N', 'types': ['Narg', 'apoC', 'Narg', 'Narg']},
                  ]
        for group in groups:
            template = Chem.MolFromSmarts(group['SMARTS'])
            types = group['types']
            for match in self.mol.GetSubstructMatches(template):
                for i, n in enumerate(types):
                    j = match[i]
                    atom = self.mol.GetAtomWithIdx(j)
                    if n is not None and not (atom.HasProp('_rType') and atom.GetProp('_rType').strip()):
                        atom.SetProp('_rType', n)
        # Generic atoms

        for atom in self.mol.GetAtoms():
            symbol = atom.GetSymbol()
            Hs = [a for a in atom.GetNeighbors() if a.GetSymbol() == 'H']
            if atom.HasProp('_rType') and atom.GetProp('_rType').strip():
                pass
            elif symbol == '*':
                atom.SetProp('_rType', 'VIRT')
            elif symbol == 'C':
                if atom.GetIsAromatic():
                    atom.SetProp('_rType', 'aroC')
                    for n in Hs:
                        n.SetProp('_rType', 'Haro')
                else:
                    atom.SetProp('_rType', 'CH' + str(len(Hs)))
            elif symbol == 'N':
                if atom.GetIsAromatic() and len(Hs) == 0:
                    atom.SetProp('_rType', 'Nhis')
                elif atom.GetIsAromatic():  # could also be NtrR...
                    atom.SetProp('_rType', 'Ntrp')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3 and len(Hs) < 3:
                    atom.SetProp('_rType', 'Nbb')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    atom.SetProp('_rType', 'Nlys')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2:
                    atom.SetProp('_rType', 'Npro')  # or Narg if the orbitals are funky...
                else:
                    raise ValueError(f'No idea what this nitrogen {atom.GetHybridization()} is')
            elif symbol == 'O':
                if atom.GetIsAromatic():
                    atom.SetProp('_rType', 'Oaro')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2:
                    atom.SetProp('_rType', 'Oet2')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    atom.SetProp('_rType', 'Oet3')
                else:
                    raise ValueError(f'No idea what this oxygen {atom.GetHybridization()} is')
            elif symbol == 'H':
                n = atom.GetNeighbors()[0]
                if n.GetSymbol() == 'C' and n.GetIsAromatic():
                    atom.SetProp('_rType', 'Haro')
                elif n.GetSymbol() == 'C':
                    atom.SetProp('_rType', 'Hapo')
                elif n.GetSymbol() == 'S':
                    atom.SetProp('_rType', 'HS')
                else:
                    atom.SetProp('_rType', 'Hpol')
            elif symbol == 'S':
                if len(Hs) == 1:
                    atom.SetProp('_rType', 'SH1')
                else:
                    atom.SetProp('_rType', 'S')
            elif symbol == 'P':
                atom.SetProp('_rType', 'Phos')
            elif symbol.upper() in element_to_type:
                atom.SetProp('_rType', element_to_type[symbol.upper()])
            else:
                warn(f'No idea what this {atom.GetSymbol()} {atom.GetHybridization()} is. assigning it REPLS')
                atom.SetProp('_rType', 'REPLS')

    def _add_genrtypes(self) -> None:
        """
        Add Rosetta Atom types to each atom.
        """
        groups = [{'name': 'carboxylate', 'SMARTS': 'C(=O)[O-]', 'types': ['COO', 'OOC', 'OOC']},
                  {'name': 'carboxylic', 'SMARTS': 'C(=O)[OH]', 'types': ['COO', 'OOC', 'OH']},
                  {'name': 'ester', 'SMARTS': 'C(=O)OC', 'types': ['COO', 'Oal', 'Oet', None]},
                  {'name': 'ester', 'SMARTS': 'C(=O)O', 'types': ['COO', 'OOC', 'OOC']},
                  {'name': '3amide', 'SMARTS': 'C(=O)[NH0]', 'types': ['CNH2', 'ONH2', 'Nad3']},
                  {'name': 'amide', 'SMARTS': 'C(=O)N', 'types': ['CNH2', 'ONH2', 'NH2O']},
                  {'name': 'keto-aldehyde', 'SMARTS': 'C(=O)', 'types': [None, 'Oal']},
                  {'name': '2amine', 'SMARTS': 'CNC', 'types': [None, 'Nam2', None]},
                  {'name': 'azo', 'SMARTS': 'NN', 'types': ['Nad3', 'Nad3']},
                  {'name': 'nitrile', 'SMARTS': 'C#N', 'types': ['CTp', 'NG1']},
                  {'name': 'imino', 'SMARTS': 'C=[NH]', 'types': [None, 'Nin']},
                  {'name': '2imino', 'SMARTS': 'C=[NH0]', 'types': [None, 'Nim']},
                  {'name': '2amine', 'SMARTS': 'CNC', 'types': [None, 'Nam', None]},
                  {'name': 'nitro', 'SMARTS': '[N+](=O)[O-]', 'types': ['NGb', 'Ont', 'Ont']},
                  {'name': 'nitro_aro', 'SMARTS': 'n(=o)o', 'types': ['NGb', 'Ont', 'Ont']},
                  {'name': 'furan', 'SMARTS': 'coc', 'types': ['aroC', 'Ofu', 'aroC']},
                  {'name': 'ether', 'SMARTS': 'COC', 'types': [None, 'Oet', None]},
                  {'name': 'hydroxyl', 'SMARTS': '[OH]', 'types': ['OH']},
                  {'name': 'guanidium', 'SMARTS': 'NC(=N)N', 'types': ['Narg', 'apoC', 'Narg', 'Narg']}
                  ]
        for group in groups:
            template = Chem.MolFromSmarts(group['SMARTS'])
            types = group['types']
            for match in self.mol.GetSubstructMatches(template):
                for i, n in enumerate(types):
                    j = match[i]
                    atom = self.mol.GetAtomWithIdx(j)
                    if n is not None and not (atom.HasProp('_rType') and atom.GetProp('_rType').strip()):
                        atom.SetProp('_rType', n)
        # Generic atoms
        for atom in self.mol.GetAtoms():
            symbol = atom.GetSymbol()
            Hs = [a for a in atom.GetNeighbors() if a.GetSymbol() == 'H']
            if atom.HasProp('_rType') and atom.GetProp('_rType').strip():
                pass
            elif symbol == '*':
                atom.SetProp('_rType', 'VIRT')
            elif symbol == 'C':
                if atom.GetIsAromatic():
                    atom.SetProp('_rType', 'aroC')
                    for n in Hs:
                        n.SetProp('_rType', 'Haro')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    if len(Hs) > 0:
                        atom.SetProp('_rType', 'CH' + str(len(Hs)))
                    else:
                        atom.SetProp('_rType', 'CS')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2:
                    if len(Hs) > 0:
                        atom.SetProp('_rType', 'CD' + str(len(Hs)))
                    else:
                        atom.SetProp('_rType', 'CD')
                elif atom.GetHybridization() == Chem.HybridizationType.SP:
                    atom.SetProp('_rType', 'CT')
                else:
                    raise ValueError(f'No idea what this carbon {atom.GetHybridization()} is')
            elif symbol == 'N':
                if atom.GetIsAromatic():
                    atom.SetProp('_rType', 'NGb')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3 and len(Hs) == 0:
                    atom.SetProp('_rType', 'NG3')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    atom.SetProp('_rType', 'Nam')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2 and len(Hs) == 0:
                    atom.SetProp('_rType', 'NG2')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2 and len(Hs) == 1:
                    atom.SetProp('_rType', 'NG21')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2 and len(Hs) == 2:
                    atom.SetProp('_rType', 'NG22')
                elif atom.GetHybridization() == Chem.HybridizationType.SP and len(Hs) == 0:
                    atom.SetProp('_rType', 'NG1')
                else:
                    raise ValueError(f'No idea what this nitrogen {atom.GetHybridization()} is')
            elif symbol == 'O':
                if atom.GetIsAromatic():
                    atom.SetProp('_rType', 'Oaro')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2 and len(Hs) == 0:
                    atom.SetProp('_rType', 'OG2')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3 and len(Hs) == 0:
                    atom.SetProp('_rType', 'OG3')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3 and len(Hs) == 1:
                    atom.SetProp('_rType', 'OG31')
                else:
                    raise ValueError(f'No idea what this oxygen {atom.GetHybridization()} is')
            elif symbol == 'H':
                n = atom.GetNeighbors()[0]
                if n.GetSymbol() == 'C' and n.GetIsAromatic():
                    atom.SetProp('_rType', 'Haro')
                elif n.GetSymbol() == 'C':
                    atom.SetProp('_rType', 'Hapo')
                elif n.GetSymbol() == 'S':
                    atom.SetProp('_rType', 'HS')
                elif n.GetSymbol() == 'N':
                    atom.SetProp('_rType', 'HN')
                elif n.GetSymbol() == 'O':
                    atom.SetProp('_rType', 'HO')
                else:
                    atom.SetProp('_rType', 'HG')
            elif symbol == 'S':
                if len(Hs) == 1:
                    atom.SetProp('_rType', 'Sth')
                elif len(Hs) == 0:
                    atom.SetProp('_rType', 'Ssl')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3 and atom.GetExplicitValence() == 6:
                    atom.SetProp('_rType', 'SG5')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    atom.SetProp('_rType', 'SG3')
                elif atom.GetHybridization() == Chem.HybridizationType.SP2:
                    atom.SetProp('_rType', 'SG2')
                else:
                    raise ValueError(f'No idea what this S {atom.GetHybridization()} is')
            elif symbol == 'P':
                if atom.GetHybridization() == Chem.HybridizationType.SP3 and atom.GetExplicitValence() == 6:
                    atom.SetProp('_rType', 'PG5')
                elif atom.GetHybridization() == Chem.HybridizationType.SP3:
                    atom.SetProp('_rType', 'PG3')
                else:
                    raise ValueError(f'No idea what this S {atom.GetHybridization()} is')
            elif symbol in ('F', 'Cl', 'Br', 'I'):
                n = atom.GetNeighbors()[0]
                if n.GetIsAromatic():
                    atom.SetProp('_rType', symbol + 'R')
                else:
                    atom.SetProp('_rType', symbol)
            else:
                raise ValueError(f'No idea what this {atom.GetSymbol()} {atom.GetHybridization()} is')

    def _fix_atom_names(self):
        elemental = defaultdict(int)
        seen = []
        for i in range(self.mol.GetNumAtoms()):
            atom = self.mol.GetAtomWithIdx(i)
            el = atom.GetSymbol()
            if el == '*':
                el = 'CONN'
            elemental[el] += 1  # compatible mol_to_params.py
            info = atom.GetPDBResidueInfo()
            lamename = el + str(elemental[el])
            while lamename in seen:
                elemental[el] += 1
                lamename = el + str(elemental[el])
            if info is None:
                atom.SetMonomerInfo(Chem.AtomPDBResidueInfo(atomName=lamename,
                                                            serialNumber=i,
                                                            residueName=self.NAME,
                                                            isHeteroAtom=True))
                seen.append(lamename)
            else:
                if info.GetName() in seen:
                    warn(f'Name clash {info.GetName()}, second one now called {lamename}')
                    info.SetName(lamename)
                    seen.append(lamename)
                else:
                    seen.append(info.GetName())

    def _add_partial_charges(self):
        demovalence = {1: 1, 2: 8, 3: 7, 4: 6, 6: 15}
        mol = Chem.Mol(self.mol)
        while True:
            try:
                AllChem.ComputeGasteigerCharges(mol, throwOnParamFailure=True)
            except ValueError as err:
                warn(f'{err.__class__.__name__}: {err}')
                dodgy = re.search('parameters for Element\: ([*\w]+)', str(err)).group(1)
                for atom in mol.GetAtoms():
                    if atom.GetSymbol() == dodgy:
                        valence = atom.GetExplicitValence()
                        atom.SetAtomicNum(demovalence[valence])
            else:
                break
        for i in range(self.mol.GetNumAtoms()):
            gc = mol.GetAtomWithIdx(i).GetDoubleProp('_GasteigerCharge')
            self.mol.GetAtomWithIdx(i).SetDoubleProp('_GasteigerCharge', gc)

