# Helper: build an invite URL with the minimum perms to read history (+ optional send)
# Usage: python scripts/print_invite_url.py <CLIENT_ID> [--send]
import sys

PERM_VIEW_CHANNELS = 1 << 10        # 1024
PERM_SEND_MESSAGES = 1 << 11        # 2048
PERM_READ_MESSAGE_HISTORY = 1 << 16 # 65536


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/print_invite_url.py <CLIENT_ID> [--send]")
        sys.exit(1)
    client_id = sys.argv[1]
    perms = PERM_VIEW_CHANNELS | PERM_READ_MESSAGE_HISTORY
    if len(sys.argv) > 2 and sys.argv[2] == "--send":
        perms |= PERM_SEND_MESSAGES
    url = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=bot&permissions={perms}"
    print(url)


if __name__ == "__main__":
    main()


