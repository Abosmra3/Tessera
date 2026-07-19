import json
import subprocess
from typing import Any


def run_powershell(command: str) -> str:
    """Run a PowerShell command and return its stdout text."""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=creationflags,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    return result.stdout.strip()


def parse_json_array(data: str) -> list[dict[str, Any]]:
    """Parse JSON output from PowerShell into a list of dictionaries."""
    if not data:
        return []

    parsed = json.loads(data)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def _is_microsoft_defender_product(name: str, path: str = "") -> bool:
    """Return True for Microsoft Defender products so they are not treated as third-party AV."""
    normalized_name = (name or "").lower()
    normalized_path = (path or "").lower()
    microsoft_markers = (
        "windows defender",
        "microsoft defender",
        "defender",
        "msmpeng",
    )
    return any(marker in normalized_name or marker in normalized_path for marker in microsoft_markers)


def _format_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def get_firewall_health_summary() -> dict[str, Any]:
    """Return a simple, reusable diagnosis for firewall and AV status."""
    firewall_output = run_powershell(
        """
        Get-NetFirewallProfile |
        Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction |
        ConvertTo-Json -Compress
        """
    )

    av_output = run_powershell(
        """
        Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct |
        Select-Object DisplayName, PathToSignedProductExe |
        ConvertTo-Json -Compress
        """
    )

    firewall_profiles = parse_json_array(firewall_output)
    av_products = parse_json_array(av_output)

    firewall_enabled = any(profile.get("Enabled") is True for profile in firewall_profiles)
    av_names = [product.get("DisplayName", "") for product in av_products if product.get("DisplayName")]
    third_party_av = []
    for product in av_products:
        display_name = product.get("DisplayName", "")
        if not display_name:
            continue
        if _is_microsoft_defender_product(display_name, product.get("PathToSignedProductExe", "")):
            continue
        if display_name not in third_party_av:
            third_party_av.append(display_name)

    third_party_av_names = _format_list(third_party_av)
    third_party_av_verb = "are" if len(third_party_av) > 1 else "is"

    if not firewall_enabled and third_party_av_names:
        reason = (
            f"Windows Firewall is disabled. {third_party_av_names} {third_party_av_verb} installed "
            "and may affect or manage firewall behavior."
        )
    elif not firewall_enabled:
        reason = "Windows Firewall is disabled."
    elif third_party_av_names:
        reason = (
            f"{third_party_av_names} {third_party_av_verb} installed and may affect or manage firewall behavior."
        )
    else:
        reason = "Windows Firewall is enabled, but the nosave rule test still failed."

    return {
        "firewall_enabled": firewall_enabled,
        "firewall_profiles": firewall_profiles,
        "av_products": av_products,
        "av_names": av_names,
        "third_party_av": third_party_av,
        "reason": reason,
    }


def main() -> None:
    try:
        summary = get_firewall_health_summary()
        firewall_profiles = summary["firewall_profiles"]
        av_names = summary["av_names"]

        print("Firewall status:")
        if not firewall_profiles:
            print("No firewall profiles were returned.")
        else:
            for profile in firewall_profiles:
                print(
                    f"- {profile.get('Name', 'Unknown')}: "
                    f"Enabled={profile.get('Enabled')}"
                )

        if summary["firewall_enabled"]:
            print("\nWindows Firewall appears enabled.")
        else:
            print("\nWindows Firewall appears disabled or unavailable.")

        if av_names:
            print("\nDetected antivirus products:")
            for name in av_names:
                print(f"- {name}")

            if summary["third_party_av"]:
                print(
                    "\nA non-Microsoft antivirus product was detected. "
                    "It may be managing firewall behavior."
                )
        else:
            print("\nNo antivirus product was detected through the SecurityCenter2 WMI class.")

        print(f"\nReason: {summary['reason']}")

    except Exception as exc:
        print(f"Error: {exc}")
        print("This script is intended for Windows environments and may require admin privileges.")


if __name__ == "__main__":
    main()
