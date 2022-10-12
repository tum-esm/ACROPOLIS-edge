import asyncio
import ssl
import json

import app.asyncio_mqtt as aiomqtt
import app.settings as settings
import app.logs as logs
import app.utils as utils
import app.database as database


def _encode_payload(payload):
    """Encode python dict into utf-8 JSON bytestring."""
    return json.dumps(payload).encode()


def _decode_payload(payload):
    """Decode python dict from utf-8 JSON bytestring."""
    return json.loads(payload.decode())


CLIENT_SETTINGS = {
    "hostname": settings.MQTT_URL,
    "port": 8883,
    "protocol": aiomqtt.ProtocolVersion.V5,
    "username": settings.MQTT_IDENTIFIER,
    "password": settings.MQTT_PASSWORD,
    "tls_params": aiomqtt.TLSParameters(tls_version=ssl.PROTOCOL_TLS),
}


async def send(payload, topic):
    """Publish a JSON message to a topic."""
    async with aiomqtt.Client(**CLIENT_SETTINGS) as client:
        await client.publish("measurements", payload=_encode_payload(payload))


async def startup():
    """Set up the MQTT client and start listening to incoming sensor measurements."""

    async def listen_and_write():

        async with aiomqtt.Client(**CLIENT_SETTINGS) as client:
            async with client.unfiltered_messages() as messages:
                await client.subscribe("measurements")
                async for message in messages:
                    payload = _decode_payload(message.payload)
                    logs.logger.info(
                        f"Received message: {payload} (topic: {message.topic})"
                    )
                    # write measurement to database
                    async with database.conn.transaction():
                        await database.conn.execute(
                            f"""
                            INSERT INTO measurements VALUES(
                                {payload['timestamp']},
                                {utils.timestamp()},
                                {payload['value']}
                            );
                        """
                        )

    # wait for messages in (unawaited) asyncio task
    loop = asyncio.get_event_loop()
    loop.create_task(listen_and_write())
