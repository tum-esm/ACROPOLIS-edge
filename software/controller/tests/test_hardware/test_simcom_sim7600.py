import pytest

from hardware.sensors.simcom_sim7600 import (find_at_port, parse_cpsi, parse_csq,
                                             parse_iccid, parse_imei,
                                             parse_operator)

# responses recorded on acropolis-4 (SIM7600E-H, firmware SIM7600M22_V2.0.1)
CSQ = "\r\n+CSQ: 25,99\r\n\r\nOK\r\n"
CPSI_LTE = "\r\n+CPSI: LTE,Online,262-03,0xC945,25885738,204,EUTRAN-BAND3,1600,5,5,-123,-951,-611,14\r\n\r\nOK\r\n"
ICCID = "\r\n+ICCID: 8934076100156729088\r\n\r\nOK\r\n"
CGSN = "\r\n860147052764394\r\n\r\nOK\r\n"
COPS = '\r\n+COPS: 0,0,"o2 - de",7\r\n\r\nOK\r\n'


@pytest.mark.github_action
def test_parse_csq() -> None:
    assert parse_csq(CSQ) == -63
    assert parse_csq("\r\n+CSQ: 99,99\r\n\r\nOK\r\n") is None
    assert parse_csq("\r\nERROR\r\n") is None


@pytest.mark.github_action
def test_parse_cpsi() -> None:
    assert parse_cpsi(CPSI_LTE) == {
        "rat": "LTE",
        "band": "EUTRAN-BAND3",
        "rsrq_db": -12.3,
        "rsrp_dbm": -95.1,
        "sinr_db": 14.0,
    }
    assert parse_cpsi("\r\n+CPSI: NO SERVICE,Online\r\n\r\nOK\r\n") == {
        "rat": "NO SERVICE"
    }
    assert parse_cpsi("\r\nERROR\r\n") == {}


@pytest.mark.github_action
def test_parse_identifiers() -> None:
    assert parse_iccid(ICCID) == "8934076100156729088"
    assert parse_imei(CGSN) == "860147052764394"
    assert parse_operator(COPS) == "o2 - de"
    assert parse_iccid("\r\nERROR\r\n") is None
    assert parse_imei("\r\nERROR\r\n") is None


@pytest.mark.github_action
def test_find_at_port(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # sysfs layout of acropolis-4: an FTDI adapter between the modem ports
    devices = tmp_path / "devices"
    for tty, vendor, interface in [("ttyUSB0", "1e0e", "00"),
                                   ("ttyUSB2", "0403", "00"),
                                   ("ttyUSB3", "1e0e", "02")]:
        usb_device = tmp_path / f"usb-{tty}"
        interface_path = usb_device / f"{tty}-interface"
        (interface_path / tty).mkdir(parents=True)
        (usb_device / "idVendor").write_text(vendor + "\n")
        (interface_path / "bInterfaceNumber").write_text(interface + "\n")
        devices.mkdir(exist_ok=True)
        (devices / tty).symlink_to(interface_path / tty)

    assert find_at_port(str(devices)) == "/dev/ttyUSB3"
    assert find_at_port(str(tmp_path / "missing")) is None
