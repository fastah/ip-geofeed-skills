# Instructions for installing and verifying `csvkit` CLI tool using Python `pipx`

Requirements: Python ≥ 3.10, avoid system Python modifications, prefer pipx, include PATH fixes, and provide OS-specific commands.

| Platform               | Best default            | Acceptable alternative | Discouraged        |
|------------------------|-------------------------|------------------------|--------------------|
| Linux (Ubuntu/Debian)  | `pipx install csvkit`   | Python virtualenv      | `sudo pip install` |
| Linux (RHEL/CentOS)    | `pipx install csvkit`   | Python virtualenv      | system `pip`       |
| macOS                  | `pipx install csvkit`   | `brew install csvkit`  | system `pip`       |
| Windows                | `pipx install csvkit`   | Python virtualenv      | global `pip`       |

End by running a version check as below, and explain how to debug if it fails or does not report a version `2.x.y`:

```shell
    csvcut --version
```
