## Contanerised AmneziaWG VPN server with [AmneziaWG-go](https://github.com/amnezia-vpn/amneziawg-go) used as a backbone.

ENVs:
| **Variable**           | **Description**                                                                                   | **Default Value**                       |
|------------------------|---------------------------------------------------------------------------------------------------|-----------------------------------------|
| `AMNEZIAWG_IP`         | IP address of the VPN server with mask.                                                           | 10.9.9.1/24 |
| `AMNEZIAWG_PORT`       | UDP port for WireGuard to use.                                                                    | 49666 |
| `AMNEZIAWG_INTERFACE`  | TUN interface name, better leave default.                                                         | awg0      |

Deploy:
```
AMNEZIAWG_IP=$YOUR_IP_WITH_MASK AMNEZIAWG_PORT=$YOUR_PORT docker compose up --force-recreate --no-deps -d
```

Add new client
```
docker exec -it amneziawg-go python3 /etc/amnezia/awgcfg.py --addcl $CLIENT_NAME
docker exec -it amneziawg-go python3 /etc/amnezia/awgcfg.py --confgen $CLIENT_NAME
docker container restart amneziawg-go
```
Need to restart container for new config to catch up.

Optionally `--allowed` flag to set list allowed IPs for the client and `--dns` flag can be passed along with `--confgen`:
```
docker exec -it amneziawg-go python3 /etc/amnezia/awgcfg.py --confgen $CLIENT_NAME --allowed 0.0.0.0/24,100.100.100.0/24 --dns 1.1.1.1
```
By default `8.8.8.8` DNS used

Delete client:
```
docker exec -it amneziawg-go python3 /etc/amnezia/awgcfg.py --delete $CLIENT_NAME
```

Build and push:
```
docker buildx build --platform linux/amd64,linux/arm64 -t fviolence/amneziawg-go:v1.0 -t fviolence/amneziawg-go:latest --push .
```

Kudos: awgcfg.py is based on [this](https://gist.github.com/Ifksitovec/21b25f8f4ab1fa71011b8984deba6b6e)