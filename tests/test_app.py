"""tests cogeo_mosaic_tiler.handlers.app."""

import os
import re
import json
import base64
import urllib

import pytest
from mock import patch
from botocore.exceptions import ClientError

from cogeo_mosaic.utils import create_mosaic
from cogeo_mosaic import version


asset1 = os.path.join(os.path.dirname(__file__), "fixtures", "cog1.tif")
asset2 = os.path.join(os.path.dirname(__file__), "fixtures", "cog2.tif")
mosaic_content = create_mosaic([asset1, asset2])
request_json = os.path.join(os.path.dirname(__file__), "fixtures", "request.json")


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set fake env to make sure we don't hit AWS services."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "jqt")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rde")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/tmp/noconfigheere")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tmp/noconfighereeither")
    monkeypatch.setenv("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    monkeypatch.setenv("MOSAIC_DEF_BUCKET", "my-bucket")


@pytest.fixture()
def event():
    """Event fixture."""
    return {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {"Host": "somewhere-over-the-rainbow.com"},
        "queryStringParameters": {},
    }


def test_version(event):
    """Test version."""
    # HACK: We import the app in a test function to make sure the boto3_session uses
    # the monkeypatched env
    from cogeo_mosaic_tiler.handlers import app

    assert app.mosaic_version == version


def test_favicon(event):
    """Test /favicon.ico route."""
    from cogeo_mosaic_tiler.handlers.app import app

    event["path"] = "/favicon.ico"
    event["httpMethod"] = "GET"

    resp = {
        "body": "",
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "text/plain",
        },
        "statusCode": 204,
    }
    res = app(event, {})
    assert res == resp


@patch("cogeo_mosaic_tiler.handlers.app._aws_put_data")
def test_add_mosaic(aws_put_data, event):
    """Test /add route."""
    from cogeo_mosaic_tiler.handlers.app import app

    event["path"] = "/add"
    event["httpMethod"] = "POST"
    event["body"] = json.dumps(mosaic_content).encode()

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }
    aws_put_data.return_value = True

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    aws_put_data.assert_called()
    aws_put_data.reset_mock()

    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps(mosaic_content).encode()).decode(
        "utf-8"
    )
    aws_put_data.return_value = True

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    aws_put_data.assert_called()
    aws_put_data.reset_mock()

    event["queryStringParameters"] = dict(
        mosaicid="b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    )
    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    aws_put_data.assert_called()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
@patch("cogeo_mosaic_tiler.handlers.app._aws_put_data")
def test_create_mosaic(aws_put_data, get_mosaic, event):
    """Test /create route."""
    from cogeo_mosaic_tiler.handlers.app import app

    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    get_mosaic.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "get_object"
    )
    aws_put_data.return_value = True

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}@1x", url_info.path)
    aws_put_data.assert_called()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
@patch("cogeo_mosaic_tiler.handlers.app._aws_put_data")
def test_create_mosaicPNG(aws_put_data, get_mosaic, event):
    """Test /create route."""
    from cogeo_mosaic_tiler.handlers.app import app

    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )
    event["queryStringParameters"] = dict(tile_format="png")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    get_mosaic.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "get_object"
    )
    aws_put_data.return_value = True

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}@1x.png", url_info.path)
    aws_put_data.assert_called()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
@patch("cogeo_mosaic_tiler.handlers.app._aws_put_data")
def test_create_mosaicMVT(aws_put_data, get_mosaic, event):
    """Test /create route."""
    from cogeo_mosaic_tiler.handlers.app import app

    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )
    event["queryStringParameters"] = dict(tile_format="mvt")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    get_mosaic.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "get_object"
    )
    aws_put_data.return_value = True

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}.mvt", url_info.path)
    aws_put_data.assert_called()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_get_mosaic_info(get_data, event):
    """Test /info route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event["path"] = "/info"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }
    statusCode = 200

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == statusCode
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "http://mymosaic.json"
    assert len(body["quadkeys"]) == 9
    assert body["layers"] == ["band1", "band2", "band3"]
    get_data.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_get_mosaic_info_mosaicid(get_data, event):
    """Test /info route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event["path"] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/info"
    event["httpMethod"] = "GET"

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }
    statusCode = 200

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == statusCode
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    assert len(body["quadkeys"]) == 9
    assert body["layers"] == ["band1", "band2", "band3"]
    get_data.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_get_mosaic_geojson_mosaicid(get_data, event):
    """Test /geojson route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event["path"] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/geojson"
    event["httpMethod"] = "GET"

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }
    statusCode = 200

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == statusCode
    body = json.loads(res["body"])
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 9
    get_data.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_get_mosaic_wmts(get_data):
    """Test /wmts route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event = {
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "wmts"},
        "path": "/wmts",
        "headers": {"host": "somewhere-over-the-rainbow.com"},
    }

    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(tile_scale="2", url="http://mymosaic.json")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/xml",
    }
    statusCode = 200

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == statusCode
    body = res["body"]
    assert "https://somewhere-over-the-rainbow.com/wmts" in body
    get_data.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_get_mosaic_wmts_mosaicid(get_data):
    """Test /wmts route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event = {
        "resource": "/{proxy+}",
        "pathParameters": {
            "proxy": "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/wmts"
        },
        "path": "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/wmts",
        "headers": {"host": "somewhere-over-the-rainbow.com"},
    }

    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(tile_scale="2")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/xml",
    }
    statusCode = 200

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == statusCode
    body = res["body"]
    assert "https://somewhere-over-the-rainbow.com/wmts" in body
    assert "99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516" in body
    get_data.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_tilejson(get_data, event):
    """Test /tilejson.json route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event = {
        "resource": "/{proxy+}",
        "pathParameters": {"proxy": "tilejson.json"},
        "path": "/tilejson.json",
        "headers": {"host": "somewhere-over-the-rainbow.com"},
    }
    event["path"] = "/tilejson.json"
    event["httpMethod"] = "GET"
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }
    res = app(event, {})
    assert res["statusCode"] == 400

    # png 256px
    event["queryStringParameters"] = dict(url="http://mymosaic.json", rescale="-1,1")

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "http://mymosaic.json"
    assert body["tilejson"] == "2.1.0"

    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}@1x"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "http://mymosaic.json"
    assert qs["rescale"][0] == "-1,1"

    # Jpeg 512px
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", tile_format="jpg", tile_scale=2
    )

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}@2x.jpg"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "http://mymosaic.json"

    event["queryStringParameters"] = dict(url="http://mymosaic.json", tile_format="pbf")

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}.pbf"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "http://mymosaic.json"


@patch("cogeo_mosaic_tiler.handlers.app.fetch_mosaic_definition")
def test_tilejson_mosaicid(get_data):
    """Test /tilejson.json route."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_data.return_value = mosaic_content

    event = {
        "resource": "/{proxy+}",
        "pathParameters": {
            "proxy": "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/tilejson.json"
        },
        "path": "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/tilejson.json",
        "headers": {"host": "somewhere-over-the-rainbow.com"},
    }
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(rescale="-1,1")

    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Origin": "*",
        "Content-Type": "application/json",
    }

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert (
        body["name"]
        == "s3://my-bucket/mosaics/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516.json.gz"
    )
    assert body["tilejson"] == "2.1.0"

    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert (
        url_info.path
        == "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/{z}/{x}/{y}@1x"
    )
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["rescale"][0] == "-1,1"


@patch("cogeo_mosaic_tiler.handlers.app.fetch_and_find_assets")
def test_API_errors(get_assets, event):
    """Test /tiles routes."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_assets.return_value = []

    # missing URL
    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    res = app(event, {})
    assert res["statusCode"] == 400
    headers = res["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert res["body"] == "Missing 'URL' parameter"

    # empty assets
    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json")
    res = app(event, {})
    assert res["statusCode"] == 204
    headers = res["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert res["body"] == "No assets found for tile 9-150-182"


@patch("cogeo_mosaic_tiler.handlers.app.fetch_and_find_assets")
def test_API_tiles(get_assets, event):
    """Test /tiles routes."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_assets.return_value = [asset1, asset2]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", pixel_selection="first"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", pixel_selection="highest"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", pixel_selection="lowest"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", pixel_selection="mean"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", pixel_selection="median"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", rescale="0,10000", indexes="1", color_map="cfastie"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182@2x.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json", rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/155/182@2x"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json", rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = f"/9/150/182"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json", rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/jpg"
    assert res["body"]

    event[
        "path"
    ] = f"/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event[
        "path"
    ] = f"/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182@2x.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/png"
    assert res["body"]

    event[
        "path"
    ] = f"/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182@2x"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "image/jpg"
    assert res["body"]


@patch("cogeo_mosaic_tiler.handlers.app.fetch_and_find_assets")
def test_API_emptytiles(get_assets, event):
    """Test /tiles routes."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_assets.return_value = [asset1, asset2]

    # empty assets
    event["path"] = f"/9/140/182.png"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json")
    res = app(event, {})
    assert res["statusCode"] == 204
    headers = res["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert res["body"] == "empty tiles"


@patch("cogeo_mosaic_tiler.handlers.app.fetch_and_find_assets")
def test_API_MVTtiles(get_assets, event):
    """Test /tiles routes."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_assets.return_value = [asset1, asset2]

    event["path"] = f"/9/150/182.pbf"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = {}
    res = app(event, {})
    assert res["statusCode"] == 400

    event["path"] = f"/9/150/182.pbf"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json", tile_size="64")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/x-protobuf"
    assert res["body"]

    event[
        "path"
    ] = f"/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182.pbf"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(url="http://mymosaic.json", tile_size="64")
    res = app(event, {})
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/x-protobuf"
    assert res["body"]


@patch("cogeo_mosaic_tiler.handlers.app.fetch_and_find_assets_point")
def test_API_points(get_assets, event):
    """Test /point routes."""
    from cogeo_mosaic_tiler.handlers.app import app

    get_assets.return_value = [asset1, asset2]

    event["path"] = f"/point"
    event["httpMethod"] = "GET"
    event["queryStringParameters"] = dict(
        url="http://mymosaic.json", lng="-73", lat="45"
    )
    res = app(event, {})
    print(res)
    assert res["statusCode"] == 200
    headers = res["headers"]
    assert headers["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["coordinates"]
    assert body["values"]
    assert len(body["values"]) == 2
