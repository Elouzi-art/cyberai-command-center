import pefile

from tests.pe_builder import CODE, Sec, make_pe


def test_builder_produces_a_parseable_pe() -> None:
    pe = pefile.PE(data=make_pe([Sec(b".text", b"\x90" * 600, CODE)]))
    assert pe.FILE_HEADER.NumberOfSections == 1 and pe.OPTIONAL_HEADER.AddressOfEntryPoint == 0x1000


def test_builder_imports_are_parseable() -> None:
    pe = pefile.PE(
        data=make_pe([Sec(b".text", b"\x90" * 600)], imports={"kernel32.dll": ["ExitProcess"]})
    )
    assert pe.DIRECTORY_ENTRY_IMPORT[0].imports[0].name == b"ExitProcess"
