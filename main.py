import aiofiles
import aiohttp
import asyncio
import json
import re
import tomllib

from datetime import datetime, timedelta, timezone

class Client:
    def __init__(self, session: aiohttp.ClientSession, token: str):
        self._session = session
        self._token = token

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    @property
    def token(self) -> str:
        return self._token

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict = None,
        data: dict = None,
    ) -> dict:
        async with self.session.request(method, url, headers=headers, data=data) as response:
            return await response.json()


class GitHubClient(Client):
    def __init__(self, session: aiohttp.ClientSession, owner: str, repo: str, token: str):
        super().__init__(session, token)
        self._owner = owner
        self._repo = repo
        if not self._check_token():
            raise ValueError("Invalid GitHub token")
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    def _check_token(self) -> bool:
        return re.match(r"^(gh[ps]_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59})$", self._token) is not None

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def repo(self) -> str:
        return self._repo

    @property
    def token(self) -> str:
        return self._token

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._session

    async def _get_issues(self, time=None) -> list[dict]:
        if time is None:
            time = (datetime.now() - timedelta(days=10)).isoformat()
        # to copy paste from
        # https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28#list-repository-issues
        api = "https://api.github.com/repos/{owner}/{repo}/issues"
        url = api.format(owner=self._owner, repo=self._repo)

        headers = self._headers.copy()
        headers["Accept"] = "application/vnd.github.v3+json"

        return await self._make_request("GET", url, headers=headers)

    async def issues_and_prs(self) -> ([(str, str, str, str, str, str)], [(str, str, str, str, str, str)]):
        all = await self._get_issues()
        issues = [i for i in all if re.match(r"^https://(api\.)?github.com/(\w+/){2,3}issues/\d+$", i.get("html_url"))]
        prs = [i for i in all if re.match(r"^https://(api\.)?github.com/(\w+/){2,3}pull/\d+$", i.get("html_url"))]
        issues = [(
            i.get("title"),
            i.get("body"),
            i.get("html_url"),
            i.get("user", {}).get("login"),
            i.get("created_at"),
            i.get("updated_at")
        ) for i in issues]
        prs = [(
            i.get("title"),
            i.get("body"),
            i.get("html_url"),
            i.get("user", {}).get("login"),
            i.get("created_at"),
            i.get("updated_at")
        ) for i in prs]

        return issues, prs

class MatrixClient(Client):
    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        homeserver: str,
        user_id: str,
        device_id: str,
        room_id: str,
    ):
        super().__init__(session, token)
        self._homeserver = homeserver
        self._user_id = user_id
        self._device_id = device_id
        self._room_id = room_id
        self._token = token

    async def login(self) -> aiohttp.ClientResponse:
        api = "/_matrix/client/v3/login"
        url = f"{self._homeserver}{api}"
        request_body = {
            "identifier": {
                "type": "m.id.user",
                "user": self._user_id,
            },
            "device_id": self._device_id,
            "token": self._token,
            "type": "m.login.token",
        }
        r = await self._make_request("POST", url, data=json.dumps(request_body))
        print(r)
        return r

    async def _get_messages(self) -> aiohttp.ClientResponse:
        api = "/_matrix/client/v3/rooms/{roomId}/messages?access_token={accessToken}"
        url = f"{self._homeserver}{api.format(roomId=self._room_id, accessToken=self._token)}"

        return await self._make_request("GET", url)

    async def _format_messages(self, r: aiohttp.ClientResponse) -> list[dict]:
        # First pass: collect display names from member events
        display_names = {}
        for event in r["chunk"]:
            if event.get("type") == "m.room.member":
                sender = event.get("sender")
                content = event.get("content", {})
                display_name = content.get("displayname")
                if sender and display_name:
                    display_names[sender] = display_name

        # Process and format the messages
        formatted_messages = []
        for event in r["chunk"]:
            # Only process message events
            if event.get("type") == "m.room.message":
                try:
                    # Extract sender info
                    sender = event.get("sender", "Unknown")

                    # Get nickname (from sender ID)
                    #nickname = sender.split(":")[0].replace("@", "") if sender != "Unknown" else "Unknown"
                    nickname = sender

                    # Get display name from collected member events
                    display_name = display_names.get(sender)

                    # Extract message content
                    content = event.get("content", {})
                    body = content.get("body", "")

                    # Check if this is a reply or thread
                    relates_to = content.get("m.relates_to", {})
                    is_reply = "m.in_reply_to" in relates_to
                    is_thread = relates_to.get("rel_type") == "m.thread"

                    # Get reply/thread context
                    reply_to_event_id = None
                    if is_thread:
                        # Thread messages can also have m.in_reply_to, prioritize thread context
                        reply_to_event_id = relates_to.get("event_id")
                    elif is_reply:
                        reply_to_event_id = relates_to.get("m.in_reply_to", {}).get("event_id")

                    # Get timestamp and event ID
                    timestamp = event.get("origin_server_ts", 0)
                    event_id = event.get("event_id", "")

                    # Get short hash (first 8 characters after the $ sign)
                    event_hash = event_id.split("$")[-1][:8] if event_id else "unknown"
                    reply_to_hash = None

                    if reply_to_event_id:
                        reply_to_hash = reply_to_event_id.split("$")[-1][:8] if reply_to_event_id else "unknown"

                    formatted_messages.append({
                        "nickname": nickname,
                        "display_name": display_name,
                        "sender": sender,
                        "body": body,
                        "timestamp": timestamp,
                        "is_reply": is_reply,
                        "is_thread": is_thread,
                        "reply_to_event_id": reply_to_event_id,
                        "event_hash": event_hash,
                        "reply_to_hash": reply_to_hash,
                        "raw_event": event
                    })
                except Exception as e:
                    print(f"Error processing event: {e}")
                    continue

        return formatted_messages

    async def get_messages(self) -> list[dict]:
        r = await self._get_messages()
        messages = await self._format_messages(r)
        messages.sort(key=lambda x: x["timestamp"])
        return messages



class Config:
    def __init__(self, filename: str = "clients.toml"):
        self.filename = filename
        self.config = None
        self.general_settings = {}
        self.client_configs = {}

    def load_config(self):
        """Load TOML configuration from file"""
        with open(self.filename, "rb") as f:
            self.config = tomllib.load(f)

        # Separate general settings from client configs
        for section_name, section_config in self.config.items():
            if section_name == "general" or section_name == "settings":
                self.general_settings = section_config
            elif isinstance(section_config, dict) and "api" in section_config:
                self.client_configs[section_name] = section_config

        return self.config

    def get_setting(self, key: str, client_name: str = None, default=None):
        """Get a setting, checking client-specific config first, then general settings"""
        # First check client-specific settings
        if client_name and client_name in self.client_configs:
            client_config = self.client_configs[client_name]
            if key in client_config:
                return client_config[key]

        # Fall back to general settings
        return self.general_settings.get(key, default)

    async def create_client(self, session: aiohttp.ClientSession, name: str, config: dict):
        """Create a client based on the API type in config"""
        api_type = config.get("api")

        if api_type == "github":
            return GitHubClient(
                session=session,
                owner=config.get("owner"),
                repo=config.get("repo"),
                token=config.get("access_token")
            )
        elif api_type == "matrix":
            matrix_config_file = self.get_setting("config", name)
            if matrix_config_file is None:
                raise ValueError("Matrix config is required")

            async with aiofiles.open(matrix_config_file) as f:
                matrix_config_contents = await f.read()
            matrix_config_contents = json.loads(matrix_config_contents)

            room_id = self.get_setting("room_id", name)

            return MatrixClient(
                session=session,
                token=matrix_config_contents["access_token"],
                homeserver=matrix_config_contents["homeserver"],
                user_id=matrix_config_contents["user_id"],
                device_id=matrix_config_contents["device_id"],
                room_id=room_id,
            )
        else:
            raise ValueError(f"Unknown API type: {api_type}")

    async def create_all_clients(self, session: aiohttp.ClientSession) -> dict:
        """Create all clients from the loaded config"""
        if self.config is None:
            self.load_config()

        clients = {}
        for section_name, section_config in self.client_configs.items():
            clients[section_name] = await self.create_client(session, section_name, section_config)

        return clients

async def main():
    config = Config("clients.toml")
    config.load_config()

    def days_ago_from_iso(iso_string):
        """Nice format, that's it
        """
        past_date = datetime.fromisoformat(iso_string)
        now = datetime.now(timezone.utc)
        if past_date.tzinfo is None:
            past_date = past_date.replace(tzinfo=timezone.utc)
        days_difference = (now - past_date).days
        return f"{days_difference} days ago: {past_date.strftime('%Y-%m-%d')}"

    async with aiohttp.ClientSession() as session:
        clients = await config.create_all_clients(session)

        print(f"# Initialized {len(clients)} clients")
        print(f"Time: {datetime.now().isoformat()}")
        print(f"Clients:")
        for section_name, client in clients.items():
            print(f"- {section_name}")
        print()

        for section_name, client in clients.items():
            # Use the name field from config, fallback to section name
            display_name = config.config[section_name].get("name", section_name)
            # we want some pseudo-markdown here
            print(f"# {display_name}")
            print()

            if isinstance(client, GitHubClient):
                issues, prs = await client.issues_and_prs()
                # Get body_limit setting for this client (with fallback to general setting)
                body_limit = config.get_setting("body_limit", section_name, 100)

                for title, body, url, user, created, updated in issues:
                    n = re.search(r"\d+$", url).group(0)
                    if body:
                        if body_limit > 0:
                            body = body[:body_limit]
                        else:
                            body = body
                    else:
                        body = "\n\n```\nNo body\n```\n"

                    print(f"## ISSUE: {n} - {title}\n")
                    print(f"- Author:\t`{user}`")
                    print(f"- URL:\t{url}")
                    print(f"- Created:\t`{days_ago_from_iso(created)}`")
                    print(f"- Updated:\t`{days_ago_from_iso(updated)}`")
                    print(f"{body}")
                    print("\n---\n")

                for title, body, url, user, created, updated in prs:
                    if body:
                        if body_limit > 0:
                            body = body[:body_limit]
                        else:
                            body = body
                    else:
                        body = "\n```\nNo body\n```"
                    n = re.search(r"\d+$", url).group(0)
                    print(f"## PR: {n} - {title}\n")
                    print(f"- Author:\t`{user}`")
                    print(f"- URL:\t{url}")
                    print(f"- Created:\t`{days_ago_from_iso(created)}`")
                    print(f"- Updated:\t`{days_ago_from_iso(updated)}`")
                    print(f"{body}")
                    print("\n---\n")

            elif isinstance(client, MatrixClient):
                # await client.login()
                messages = await client.get_messages()


                print("```log")
                for msg in messages:
                    # Format timestamp
                    timestamp = datetime.fromtimestamp(msg["timestamp"] / 1000)
                    time_str = timestamp.strftime("%H:%M:%S")

                    # Format the message based on type
                    hash_prefix = f"[{time_str}] ({msg['event_hash']}) <{msg['nickname']}>"

                    if msg["is_thread"] and msg["reply_to_hash"]:
                        print(f"{hash_prefix} (Th: {msg['reply_to_hash']}) {msg['body']}")
                    elif msg["is_reply"] and msg["reply_to_hash"]:
                        print(f"{hash_prefix} (Re: {msg['reply_to_hash']}): {msg['body']}")
                    else:
                        print(f"{hash_prefix}: {msg['body']}")

                print("```")


if __name__ == "__main__":
    asyncio.run(main())
