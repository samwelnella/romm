import pytest

from ..scan import ScanStats, _should_scan_rom


def test_scan_stats():
    stats = ScanStats()
    assert stats.scanned_platforms == 0
    assert stats.added_platforms == 0
    assert stats.metadata_platforms == 0
    assert stats.scanned_roms == 0
    assert stats.added_roms == 0
    assert stats.metadata_roms == 0
    assert stats.scanned_firmware == 0
    assert stats.added_firmware == 0

    stats.scanned_platforms += 1
    stats.added_platforms += 1
    stats.metadata_platforms += 1
    stats.scanned_roms += 1
    stats.added_roms += 1
    stats.metadata_roms += 1
    stats.scanned_firmware += 1
    stats.added_firmware += 1

    assert stats.scanned_platforms == 1
    assert stats.added_platforms == 1
    assert stats.metadata_platforms == 1
    assert stats.scanned_roms == 1
    assert stats.added_roms == 1
    assert stats.metadata_roms == 1
    assert stats.scanned_firmware == 1
    assert stats.added_firmware == 1


def test_merging_scan_stats():
    stats = ScanStats(
        scanned_platforms=1,
        added_platforms=2,
        metadata_platforms=3,
        scanned_roms=4,
        added_roms=5,
        metadata_roms=6,
        scanned_firmware=7,
        added_firmware=8,
    )

    stats2 = ScanStats(
        scanned_platforms=10,
        added_platforms=11,
        metadata_platforms=12,
        scanned_roms=13,
        added_roms=14,
        metadata_roms=15,
        scanned_firmware=16,
        added_firmware=17,
    )

    stats += stats2

    assert stats.scanned_platforms == 11
    assert stats.added_platforms == 13
    assert stats.metadata_platforms == 15
    assert stats.scanned_roms == 17
    assert stats.added_roms == 19
    assert stats.metadata_roms == 21
    assert stats.scanned_firmware == 23
    assert stats.added_firmware == 25

    stats3 = {}
    with pytest.raises(NotImplementedError):
        stats += stats3


def test_should_scan_rom():
    pass
