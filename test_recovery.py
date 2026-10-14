import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

import main
from ai_client import create_json_response
from data_layer import DataTransformer, ShopifyClient, ShopifyConfig
from ai_engine import run_price_elasticity


@pytest.fixture
def client():
    # Do not execute production startup hooks or contact live services.
    return TestClient(main.app)


def database_with(rows):
    db = Mock()
    db.table.return_value = db
    db.select.return_value = db
    db.eq.return_value = db
    db.execute.return_value = SimpleNamespace(data=rows)
    return db


def test_database_failure_returns_safe_json_and_cors(client, monkeypatch):
    db = database_with([])
    db.execute.side_effect = APIError({"message": "private credential diagnostic", "code": "401", "details": "secret", "hint": ""})
    monkeypatch.setattr(main, "get_supabase", lambda: db)
    r = client.post('/auth/login', json={"email": "test@example.invalid", "password": "invalid"}, headers={"Origin": "https://opsintelligence.org"})
    assert r.status_code == 503
    assert r.headers['access-control-allow-origin'] == '*'
    assert r.json()['code'] == 'account_service_unavailable'
    assert 'secret' not in r.text and 'diagnostic' not in r.text


def test_login_success_and_wrong_password(client, monkeypatch):
    db = database_with([{"email": "test@example.invalid", "name": "Test", "password_hash": main.hash_password('correct-password'), "plan": "free"}])
    monkeypatch.setattr(main, 'get_supabase', lambda: db)
    monkeypatch.setattr(main, 'get_user_billing_state', lambda _: {"plan": "free"})
    assert client.post('/auth/login', json={"email": "test@example.invalid", "password": "wrong"}).status_code == 401
    r = client.post('/auth/login', json={"email": "TEST@example.invalid", "password": "correct-password"})
    assert r.status_code == 200 and r.json()['token']
    assert 'password_hash' not in r.text


def test_long_or_invalid_password_hash_is_not_a_500():
    assert not main.verify_password('a' * 100, main.hash_password('normal'))
    assert not main.verify_password('password', 'malformed')


def test_interrupted_connection_is_safe_and_read_retry_is_bounded(client, monkeypatch):
    db = database_with([])
    db.execute.side_effect = httpx.RemoteProtocolError('private upstream diagnostic')
    monkeypatch.setattr(main, 'get_supabase', lambda: db)
    response = client.post('/auth/login', json={'email': 'test@example.invalid', 'password': 'invalid'}, headers={'Origin': 'https://opsintelligence.org'})
    assert response.status_code == 503
    assert response.headers['access-control-allow-origin'] == '*'
    assert 'private' not in response.text
    handler = Mock(side_effect=[httpx.RemoteProtocolError('disconnected'), httpx.Response(200)])
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', handler)
    with main.AccountTransport() as transport:
        assert transport.handle_request(httpx.Request('GET', 'https://db.invalid/users')).status_code == 200
        assert handler.call_count == 2
        handler.reset_mock(side_effect=True)
        handler.side_effect = httpx.RemoteProtocolError('disconnected')
        with pytest.raises(httpx.RemoteProtocolError):
            transport.handle_request(httpx.Request('POST', 'https://db.invalid/users'))
        assert handler.call_count == 1
        handler.reset_mock()
        with pytest.raises(httpx.RemoteProtocolError):
            transport.handle_request(httpx.Request('GET', 'https://db.invalid/users'))
        assert handler.call_count == 2


def test_public_shop_page_never_mints_account_token(client, monkeypatch):
    lookup = Mock(side_effect=AssertionError('Unauthenticated store lookup'))
    monkeypatch.setattr(main, 'find_shopify_store_by_domain', lookup)
    r = client.get('/shopify/app?shop=test-shop.myshopify.com')
    assert r.status_code == 200
    assert '/shopify/app/bootstrap' in r.text
    assert 'app_token=' not in r.text
    lookup.assert_not_called()


def test_embedded_token_cannot_access_web_account(client):
    token = main.create_shopify_embedded_token('test@example.invalid', 'test-shop.myshopify.com')
    r = client.get('/auth/me', headers={'Authorization': 'Bearer ' + token})
    assert r.status_code == 401


def test_shopify_bootstrap_rejects_forged_token(client, monkeypatch):
    monkeypatch.setattr(main, 'SHOPIFY_API_KEY', 'client-id')
    monkeypatch.setattr(main, 'SHOPIFY_API_SECRET', 'test-secret')
    exchange = Mock()
    monkeypatch.setattr(main.requests, 'post', exchange)
    r = client.post('/shopify/app/bootstrap', json={'shop': 'test-shop'}, headers={'Authorization': 'Bearer forged'})
    assert r.status_code == 401
    exchange.assert_not_called()


def test_shopify_bootstrap_valid_session(client, monkeypatch):
    monkeypatch.setattr(main, 'SHOPIFY_API_KEY', 'client-id')
    monkeypatch.setattr(main, 'SHOPIFY_API_SECRET', 'test-secret')
    now = datetime.now(timezone.utc)
    token = jwt.encode({'aud': 'client-id', 'iss': 'https://test-shop.myshopify.com/admin', 'dest': 'https://test-shop.myshopify.com', 'nbf': now, 'exp': now + timedelta(minutes=1)}, 'test-secret', algorithm='HS256')
    response = Mock(); response.json.return_value = {'access_token': 'private', 'scope': 'read_orders'}
    monkeypatch.setattr(main.requests, 'post', lambda *a, **kw: response)
    monkeypatch.setattr(main, 'ensure_shopify_user', lambda *a: {'email': 'test@example.invalid'})
    r = client.post('/shopify/app/bootstrap', json={'shop': 'test-shop'}, headers={'Authorization': 'Bearer ' + token})
    assert r.status_code == 200 and r.json()['url'].startswith('/shopify/app?')
    assert 'private' not in r.text


def test_admin_store_url_normalizes():
    assert main.normalize_shop_domain('https://admin.shopify.com/store/example-store/orders') == 'example-store.myshopify.com'


def test_astra_request_contract():
    sdk = Mock()
    sdk.responses.create.return_value = SimpleNamespace(status='completed', output_text='{"answer":"OK"}')
    parsed, _ = create_json_response(model='gpt-6-astra', system='JSON only', user='test', client=sdk)
    kwargs = sdk.responses.create.call_args.kwargs
    assert parsed['answer'] == 'OK'
    assert 'temperature' not in kwargs and kwargs['reasoning']['effort'] == 'low'
    assert kwargs['store'] is False
    sdk.responses.create.return_value.status = 'incomplete'
    with pytest.raises(ValueError):
        create_json_response(model='gpt-6-astra', system='JSON only', user='test', client=sdk)


def test_unknown_cost_does_not_become_profit():
    df = DataTransformer.products_to_dataframe([{'id': 1, 'title': 'Unknown cost', 'price': '50'}])
    assert pd.isna(df.iloc[0]['cost']) and pd.isna(df.iloc[0]['margin_pct'])
    result = run_price_elasticity(pd.DataFrame({'product_title': [], 'total_price': []}), df)
    assert result['products'][0]['recommendation'] == 'add_cost_data'
    assert result['products'][0]['margin_pct'] is None


def test_zero_cost_is_distinct_from_missing():
    df = DataTransformer.products_to_dataframe([{'id': 1, 'title': 'Free input', 'price': '50', 'cost_per_item': 0}])
    assert df.iloc[0]['cost'] == 0 and df.iloc[0]['margin_pct'] == 100


def test_inventory_cost_fetch(monkeypatch):
    c = ShopifyClient(ShopifyConfig(shop_domain='test.myshopify.com', access_token='test', use_mock=False))
    product = Mock(links={}); product.json.return_value = {'products': [{'variants': [{'inventory_item_id': 42}]}]}
    costs = Mock(); costs.json.return_value = {'inventory_items': [{'id': 42, 'cost': '12.50'}]}
    monkeypatch.setattr(c, '_get', Mock(side_effect=[product, costs]))
    assert c.fetch_products()[0]['variants'][0]['cost'] == '12.50'


def test_token_refresh_persists_new_pair_before_use(monkeypatch):
    store = {'platform': 'shopify', 'domain': 'test.myshopify.com', 'access_token': 'old', 'refresh_token': 'old-refresh', 'token_expires_at': 0}
    monkeypatch.setattr(main, 'get_supabase', lambda: database_with([{'stores': [store]}]))
    response = Mock(status_code=200)
    response.json.return_value = {'access_token': 'new', 'refresh_token': 'new-refresh', 'expires_in': 3600}
    post = Mock(return_value=response)
    monkeypatch.setattr(main.requests, 'post', post)
    save = Mock(); monkeypatch.setattr(main, 'save_shopify_store', save)
    updated = main.refresh_shopify_store('test@example.invalid', store)
    assert post.call_args.kwargs['data']['grant_type'] == 'refresh_token'
    assert save.call_args.args[4]['refresh_token'] == 'new-refresh'
    assert updated['access_token'] == 'new'


def test_public_store_never_exposes_refresh_tokens():
    value = main.public_store({'access_token': 'secret-a', 'refresh_token': 'secret-b', 'domain': 'test.myshopify.com'})
    assert 'secret' not in json.dumps(value)
