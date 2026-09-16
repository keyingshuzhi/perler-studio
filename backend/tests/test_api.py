from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.main import create_app
from app.services.palette_service import get_palette_service
from app.services.storage_service import StorageService, utc_now


def _png() -> bytes:
    image = Image.new("RGBA", (4, 4), "#D94E30")
    image.putpixel((3, 3), (0, 0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _register(client: TestClient, email: str = "creator@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password-123", "display_name": "拼豆创作者"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_upload_generate_edit_project_and_export(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        client.headers.update(_register(client))
        presets = client.get("/api/v1/presets/grids")
        assert presets.status_code == 200
        assert any(item["id"] == "phone_charm_mini" for item in presets.json()["data"]["items"])
        assert presets.json()["data"]["items"][0]["dimensions"]["2.6"]["width_mm"] == 41.6
        phone_charm = next(item for item in presets.json()["data"]["items"] if item["id"] == "phone_charm_mini")
        badge = next(item for item in presets.json()["data"]["items"] if item["id"] == "badge_midi")
        assert phone_charm["recommended_bead_size_mm"] == 2.6
        assert badge["recommended_bead_size_mm"] == 5.0
        assert (phone_charm["grid_width"], phone_charm["grid_height"]) != (badge["grid_width"], badge["grid_height"])

        calibrated_palette = client.post(
            "/api/v1/palettes",
            json={
                "id": "lab-sample",
                "name": "LAB Sample",
                "brand": "Test",
                "calibration": {"source": "test sample measurement"},
                "colors": [
                    {
                        "code": "R1",
                        "name_zh": "红",
                        "hex": "#FF0000",
                        "rgb": [255, 0, 0],
                        "measured_lab": [53.24, 80.09, 67.2],
                    }
                ],
            },
        )
        assert calibrated_palette.status_code == 201, calibrated_palette.text
        assert calibrated_palette.json()["data"]["colorimetry_status"] == "measured_lab"
        assert calibrated_palette.json()["data"]["measurement_coverage_percent"] == 100

        uploaded = client.post("/api/v1/images/upload", files={"file": ("pattern.png", _png(), "image/png")})
        assert uploaded.status_code == 201
        image_id = uploaded.json()["data"]["image_id"]

        preview = client.post(
            "/api/v1/patterns/preview",
            json={
                "image_id": image_id,
                "grid_width": 4,
                "grid_height": 4,
                "resize_mode": "pixel",
                "max_colors": 4,
                "conversion_preset": "portrait",
                "subject_crop": True,
                "focus_x": 0.5,
                "focus_y": 0.5,
                "background_weaken": 0.35,
                "detail_priorities": ["facial", "outline"],
            },
        )
        assert preview.status_code == 200, preview.text
        preview_data = preview.json()["data"]
        assert len(preview_data["cells"]) == 16
        assert len(preview_data["diagnostics"]["cell_delta_e_00_tenths"]) == 16
        assert preview_data["settings"]["distance_method"] == "ciede2000"
        assert preview_data["settings"]["include_special_colors"] is False
        assert preview_data["settings"]["structure_aware"] is True
        assert preview_data["color_report"]["matching_metric"] == "ciede2000"
        assert preview_data["color_report"]["quality_basis"] == "screen_rgb"
        assert preview_data["color_report"]["matching_color_basis"] == "screen_rgb"
        assert preview_data["diagnostics"]["quality_basis"] == "screen_rgb"
        assert preview_data["color_report"]["eligible_palette_color_count"] == 221
        assert preview_data["color_report"]["oracle_palette_color_count"] == 221
        assert preview_data["color_report"]["oracle_p95_delta_e_00"] <= preview_data["color_report"]["p95_delta_e_00"]
        assert preview_data["color_report"]["p95_oracle_gap"] >= 0
        assert "cleanup_adjusted_cell_count" in preview_data["color_report"]
        assert "cleanup_adjusted_percent" in preview_data["color_report"]
        assert preview_data["color_report"]["structure_aware_enabled"] is True
        assert "structure_protected_average_delta_e_00" in preview_data["color_report"]
        assert "id" not in preview_data

        generated = client.post(
            "/api/v1/patterns/generate",
            json={
                "image_id": image_id,
                "grid_width": 4,
                "grid_height": 4,
                "resize_mode": "pixel",
                "max_colors": 4,
                "transparent_background": True,
            },
        )
        assert generated.status_code == 201, generated.text
        pattern = generated.json()["data"]
        assert pattern["palette_id"] == "mard-291"
        assert pattern["statistics"]["total_beads"] == 15
        production = client.get(
            f"/api/v1/patterns/{pattern['id']}/production-plan",
            params={"board_template_id": "midi-square-29", "strategy": "rows", "beads_per_hour": 300},
        )
        assert production.status_code == 200, production.text
        production_plan = production.json()["data"]
        assert production_plan["board_template"]["usable_holes"] == 841
        assert production_plan["assembly"]["boards"][0]["bead_count"] == 15
        assert production_plan["make_steps"][0]["id"].startswith("rows:")

        inventory_limited = client.post(
            "/api/v1/patterns/generate",
            json={
                "image_id": image_id,
                "grid_width": 4,
                "grid_height": 4,
                "resize_mode": "pixel",
                "transparent_background": True,
                "inventory": [{"color_code": "A1", "quantity": 20}],
                "inventory_mode": "only",
            },
        )
        assert inventory_limited.status_code == 201, inventory_limited.text
        inventory_pattern = inventory_limited.json()["data"]
        assert set(inventory_pattern["cells"]) == {"A1", None}
        assert inventory_pattern["color_report"]["inventory"]["enabled"] is True
        assert inventory_pattern["color_report"]["inventory"]["missing_colors"] == []

        blank = client.post(
            "/api/v1/patterns/blank",
            json={"grid_width": 8, "grid_height": 8, "palette_id": "mard-291"},
        )
        assert blank.status_code == 201, blank.text
        blank_pattern = blank.json()["data"]
        assert blank_pattern["image_id"] == ""
        assert blank_pattern["statistics"]["total_beads"] == 0
        painted_blank = client.put(
            f"/api/v1/patterns/{blank_pattern['id']}",
            json={"base_revision": 1, "changes": [{"index": 0, "before": None, "after": "A1"}]},
        )
        assert painted_blank.status_code == 200, painted_blank.text
        assert painted_blank.json()["data"]["statistics"]["total_beads"] == 1
        assert painted_blank.json()["data"]["color_report"]["quality_label"] == "原创设计"
        assert painted_blank.json()["data"]["color_report"]["oracle_p95_delta_e_00"] is None

        template = client.post(
            "/api/v1/patterns/template",
            json={"template_id": "heart-charm", "palette_id": "mard-291", "foreground_code": "A1", "accent_code": "B1"},
        )
        assert template.status_code == 201, template.text
        template_pattern = template.json()["data"]
        assembly = client.get(
            f"/api/v1/patterns/{template_pattern['id']}/assembly-plan?board_width=4&board_height=4&overlap=1"
        )
        assert assembly.status_code == 200, assembly.text
        assert assembly.json()["data"]["board_count"] > 1

        text_pattern = client.post(
            "/api/v1/patterns/text",
            json={
                "text": "AB-1",
                "style": "keychain",
                "palette_id": "mard-291",
                "foreground_code": "A1",
                "accent_code": "B1",
            },
        )
        assert text_pattern.status_code == 201, text_pattern.text
        assert text_pattern.json()["data"]["settings"]["text"] == "AB-1"

        changed = client.put(
            f"/api/v1/patterns/{pattern['id']}",
            json={
                "base_revision": 1,
                "changes": [{"index": 0, "before": pattern["cells"][0], "after": None}],
            },
        )
        assert changed.status_code == 200
        assert changed.json()["data"]["statistics"]["total_beads"] == 14
        assert changed.json()["data"]["color_report"]["matching_metric"] == "ciede2000"
        assert changed.json()["data"]["color_report"]["oracle_palette_color_count"] == 221

        regenerated = client.post(
            f"/api/v1/patterns/{pattern['id']}/regenerate",
            json={
                "image_id": image_id,
                "grid_width": 4,
                "grid_height": 4,
                "resize_mode": "pixel",
                "max_colors": 4,
                "transparent_background": True,
            },
        )
        assert regenerated.status_code == 200, regenerated.text
        assert regenerated.json()["data"]["id"] == pattern["id"]
        assert regenerated.json()["data"]["revision"] == 3

        project = client.post("/api/v1/projects", json={"name": "测试图纸", "pattern_id": pattern["id"]})
        assert project.status_code == 201
        version = client.post(f"/api/v1/projects/{project.json()['data']['id']}/versions", json={"label": "交付前"})
        assert version.status_code == 201, version.text
        versions = client.get(f"/api/v1/projects/{project.json()['data']['id']}/versions")
        assert versions.status_code == 200
        assert versions.json()["data"][0]["label"] == "交付前"
        version_detail = client.get(
            f"/api/v1/projects/{project.json()['data']['id']}/versions/{version.json()['data']['id']}"
        )
        assert version_detail.status_code == 200, version_detail.text
        assert version_detail.json()["data"]["pattern"]["cells"] == pattern["cells"]
        automatic_version = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/versions", json={"automatic": True}
        )
        assert automatic_version.status_code == 201, automatic_version.text
        assert automatic_version.json()["data"]["id"] == version.json()["data"]["id"]
        restored = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/versions/{version.json()['data']['id']}/restore"
        )
        assert restored.status_code == 200, restored.text
        restored_auto_version = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/versions", json={"automatic": True}
        )
        assert restored_auto_version.status_code == 201, restored_auto_version.text
        assert restored_auto_version.json()["data"]["automatic"] is True
        share = client.post(f"/api/v1/projects/{project.json()['data']['id']}/shares", json={})
        assert share.status_code == 201, share.text
        public_share = client.get(f"/api/v1/shares/{share.json()['data']['token']}")
        assert public_share.status_code == 200
        owner_authorization = client.headers["authorization"]
        client.headers.pop("authorization")
        assert client.get(public_share.json()["data"]["pattern"]["preview_url"]).status_code == 200
        assert client.get(pattern["preview_url"]).status_code == 401
        pinned_comment = client.post(
            f"/api/v1/shares/{share.json()['data']['token']}/comments",
            json={"message": "这里的轮廓请更圆润", "cell_index": 5},
        )
        assert pinned_comment.status_code == 200, pinned_comment.text
        comment = pinned_comment.json()["data"]["share"]["comments"][0]
        assert (comment["row"], comment["column"]) == (2, 2)
        client.headers["Authorization"] = owner_authorization
        confirmation = client.post(
            f"/api/v1/shares/{share.json()['data']['token']}/confirmation",
            json={"decision": "approved", "comment": "可以制作"},
        )
        assert confirmation.status_code == 200, confirmation.text
        assert confirmation.json()["data"]["share"]["confirmation"]["decision"] == "approved"
        duplicate = client.post(f"/api/v1/projects/{project.json()['data']['id']}/duplicate")
        assert duplicate.status_code == 201
        assert duplicate.json()["data"]["pattern_id"] != pattern["id"]
        export = client.post(
            "/api/v1/exports/png",
            json={
                "project_id": project.json()["data"]["id"],
                "cell_size_px": 16,
                "show_symbols": False,
                "include_legend": False,
            },
        )
        assert export.status_code == 200, export.text
        assert client.get(export.json()["data"]["file_url"]).status_code == 200
        pdf_export = client.post(
            "/api/v1/exports/pdf",
            json={"project_id": project.json()["data"]["id"], "mode": "single", "show_symbols": True},
        )
        assert pdf_export.status_code == 200, pdf_export.text
        assert client.get(pdf_export.json()["data"]["file_url"]).content.startswith(b"%PDF")
        guide_export = client.post(
            "/api/v1/exports/pdf",
            json={
                "project_id": project.json()["data"]["id"],
                "mode": "guide",
                "assembly_board_width": 29,
                "assembly_board_height": 29,
                "show_symbols": True,
            },
        )
        assert guide_export.status_code == 200, guide_export.text
        assert client.get(guide_export.json()["data"]["file_url"]).content.startswith(b"%PDF")
        svg_export = client.post(
            "/api/v1/exports/svg",
            json={
                "project_id": project.json()["data"]["id"],
                "cell_size_px": 24,
                "show_symbols": True,
                "symbol_mode": "color_code",
                "include_legend": True,
            },
        )
        assert svg_export.status_code == 200, svg_export.text
        svg = client.get(svg_export.json()["data"]["file_url"]).content
        used_code = next(cell for cell in changed.json()["data"]["cells"] if cell is not None)
        assert svg.startswith(b'<?xml version="1.0"')
        assert f">{used_code}<".encode() in svg
        assert b'<rect class="cell"' in svg
        removed = client.delete(f"/api/v1/projects/{project.json()['data']['id']}")
        assert removed.status_code == 204
        remaining_projects = client.get("/api/v1/projects").json()["data"]
        assert all(item["id"] != project.json()["data"]["id"] for item in remaining_projects)
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_accounts_require_authentication_and_isolate_project_records(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/projects").status_code == 401

        client.headers.update(_register(client, "owner@example.com"))
        created = client.post("/api/v1/patterns/blank", json={"grid_width": 4, "grid_height": 4})
        assert created.status_code == 201, created.text
        project = client.post("/api/v1/projects", json={"name": "私有图纸", "pattern_id": created.json()["data"]["id"]})
        assert project.status_code == 201, project.text
        project_page = client.get("/api/v1/projects/page", params={"page_size": 1})
        assert project_page.status_code == 200, project_page.text
        assert project_page.json()["data"]["library_total"] == 1
        assert project_page.json()["data"]["items"][0]["id"] == project.json()["data"]["id"]

        client.headers.update(_register(client, "other@example.com"))
        assert client.get(f"/api/v1/projects/{project.json()['data']['id']}").status_code == 404
        assert client.get("/api/v1/projects").json()["data"] == []
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_first_local_account_claims_legacy_projects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    storage = StorageService(get_settings())
    legacy_project = {
        "id": storage.new_id("pro"),
        "name": "升级前的图纸",
        "description": None,
        "pattern_id": None,
        "editor_settings": {},
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    storage.save_project(legacy_project)

    with TestClient(create_app()) as client:
        client.headers.update(_register(client, "legacy@example.com"))
        projects = client.get("/api/v1/projects")
        assert projects.status_code == 200
        assert [item["id"] for item in projects.json()["data"]] == [legacy_project["id"]]
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_built_in_admin_uses_account_login_and_can_change_password(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    with TestClient(create_app()) as client:
        first_login = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin"})
        assert first_login.status_code == 200, first_login.text
        assert first_login.json()["data"]["user"]["role"] == "admin"
        assert first_login.json()["data"]["user"]["email"] == "admin"
        headers = {"Authorization": f"Bearer {first_login.json()['data']['access_token']}"}

        changed = client.put(
            "/api/v1/auth/me/password",
            json={"current_password": "admin", "new_password": "admin-password-456"},
            headers=headers,
        )
        assert changed.status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin"}).status_code == 401
        renewed = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin-password-456"})
        assert renewed.status_code == 200, renewed.text
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_admin_user_management_and_publication_review(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    monkeypatch.setenv("INITIAL_ADMIN_EMAILS", "admin@example.com")
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    with TestClient(create_app()) as client:
        admin_headers = _register(client, "admin@example.com")
        assert client.get("/api/v1/auth/me", headers=admin_headers).json()["data"]["role"] == "admin"
        creator_headers = _register(client, "creator@example.com")
        assert client.get("/api/v1/auth/me", headers=creator_headers).json()["data"]["role"] == "user"
        assert client.get("/api/v1/admin/users", headers=creator_headers).status_code == 403

        blank = client.post("/api/v1/patterns/blank", json={"grid_width": 4, "grid_height": 4}, headers=creator_headers)
        assert blank.status_code == 201, blank.text
        painted = client.put(
            f"/api/v1/patterns/{blank.json()['data']['id']}",
            json={"base_revision": 1, "changes": [{"index": 0, "before": None, "after": "A1"}]},
            headers=creator_headers,
        )
        assert painted.status_code == 200, painted.text
        project = client.post(
            "/api/v1/projects",
            json={"name": "待审核作品", "pattern_id": blank.json()["data"]["id"]},
            headers=creator_headers,
        )
        assert project.status_code == 201, project.text
        finished_photo = client.post(
            "/api/v1/images/upload",
            files={"file": ("finished.png", _png(), "image/png")},
            headers=creator_headers,
        )
        assert finished_photo.status_code == 201, finished_photo.text
        oversized_description = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/publications",
            json={"title": "简介长度校验", "description": "拼" * 51},
            headers=creator_headers,
        )
        assert oversized_description.status_code == 422
        submitted = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/publications",
            json={
                "title": "我的第一张拼豆图纸",
                "description": "拼" * 50,
                "tags": ["挂件", "审核测试"],
                "finished_image_id": finished_photo.json()["data"]["image_id"],
            },
            headers=creator_headers,
        )
        assert submitted.status_code == 201, submitted.text
        publication = submitted.json()["data"]
        assert publication["status"] == "pending"
        assert publication["description"] == "拼" * 50
        owner_page = client.get("/api/v1/publications/mine/page", params={"page_size": 1}, headers=creator_headers)
        assert owner_page.status_code == 200, owner_page.text
        assert owner_page.json()["data"]["total"] == 1
        assert owner_page.json()["data"]["status_counts"]["pending"] == 1

        queue = client.get("/api/v1/admin/publications?status=pending", headers=admin_headers)
        assert queue.status_code == 200
        assert [item["id"] for item in queue.json()["data"]] == [publication["id"]]
        assert queue.json()["data"][0]["preview_url"]
        assert queue.json()["data"][0]["grid_width"] == 4
        assert queue.json()["data"][0]["grid_height"] == 4
        assert queue.json()["data"][0]["total_beads"] == 1
        assert queue.json()["data"][0]["used_color_count"] == 1
        assert queue.json()["data"][0]["review_ready"] is True
        queue_page = client.get(
            "/api/v1/admin/publications/page", params={"status": "pending", "page_size": 1}, headers=admin_headers
        )
        assert queue_page.status_code == 200, queue_page.text
        assert queue_page.json()["data"]["total"] == 1
        assert queue_page.json()["data"]["library_total"] == 1
        searchable_values = [
            "第一张",
            "拼" * 10,
            "审核测试",
            "拼豆创作者",
            project.json()["data"]["id"],
            blank.json()["data"]["id"],
            publication["id"],
        ]
        for search_query in searchable_values:
            search_result = client.get(
                "/api/v1/admin/publications/page",
                params={"status": "pending", "query": search_query, "page_size": 1},
                headers=admin_headers,
            )
            assert search_result.status_code == 200, search_result.text
            assert search_result.json()["data"]["total"] == 1
            assert search_result.json()["data"]["library_total"] == 1
            assert search_result.json()["data"]["items"][0]["id"] == publication["id"]
        no_search_match = client.get(
            "/api/v1/admin/publications/page",
            params={"status": "pending", "query": "%", "page_size": 1},
            headers=admin_headers,
        )
        assert no_search_match.status_code == 200, no_search_match.text
        assert no_search_match.json()["data"]["total"] == 0
        assert no_search_match.json()["data"]["library_total"] == 1
        assert no_search_match.json()["data"]["items"] == []
        legacy_search = client.get(
            "/api/v1/admin/publications",
            params={"status": "pending", "query": "审核测试"},
            headers=admin_headers,
        )
        assert legacy_search.status_code == 200, legacy_search.text
        assert [item["id"] for item in legacy_search.json()["data"]] == [publication["id"]]
        admin_finished_photo_url = queue.json()["data"][0]["finished_photo_preview_url"]
        assert admin_finished_photo_url
        assert client.get(admin_finished_photo_url, headers=admin_headers).status_code == 200
        assert client.get(f"/api/v1/admin/publications/{publication['id']}", headers=creator_headers).status_code == 403
        admin_detail = client.get(f"/api/v1/admin/publications/{publication['id']}", headers=admin_headers)
        assert admin_detail.status_code == 200, admin_detail.text
        detail = admin_detail.json()["data"]
        assert detail["publication"]["id"] == publication["id"]
        assert detail["project"]["name"] == "待审核作品"
        assert detail["pattern"]["grid_width"] == 4
        assert detail["pattern"]["grid_height"] == 4
        assert detail["pattern"]["statistics"]["total_beads"] == 1
        assert detail["pattern"]["statistics"]["colors"][0]["color_code"] == "A1"
        assert detail["pattern"]["preview_url"]
        assert client.get(detail["pattern"]["preview_url"], headers=admin_headers).status_code == 200
        assert detail["finished_photo_preview_url"] == admin_finished_photo_url
        assert detail["review_readiness"]["can_approve"] is True
        missing_rejection_reason = client.post(
            f"/api/v1/admin/publications/{publication['id']}/review",
            json={"decision": "rejected"},
            headers=admin_headers,
        )
        assert missing_rejection_reason.status_code == 422
        incomplete_compliance_review = client.post(
            f"/api/v1/admin/publications/{publication['id']}/review",
            json={"decision": "approved", "checks": ["pattern_content"]},
            headers=admin_headers,
        )
        assert incomplete_compliance_review.status_code == 422
        approved = client.post(
            f"/api/v1/admin/publications/{publication['id']}/review",
            json={
                "decision": "approved",
                "note": "图纸清晰，可以公开",
                "checks": ["pattern_content", "metadata", "rights_privacy"],
            },
            headers=admin_headers,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["status"] == "approved"
        assert approved.json()["data"]["review_checks"] == ["pattern_content", "metadata", "rights_privacy"]
        approved_search = client.get(
            "/api/v1/admin/publications/page",
            params={"status": "approved", "query": "挂件"},
            headers=admin_headers,
        )
        assert approved_search.status_code == 200, approved_search.text
        assert approved_search.json()["data"]["total"] == 1
        assert approved_search.json()["data"]["library_total"] == 1
        assert approved_search.json()["data"]["items"][0]["id"] == publication["id"]

        public = client.get(f"/api/v1/publications/{publication['public_token']}")
        assert public.status_code == 200, public.text
        preview_url = public.json()["data"]["pattern"]["preview_url"]
        assert "preview_style=solid-gridless-v1" in preview_url
        assert client.get(preview_url).status_code == 200
        assert client.get(blank.json()["data"]["preview_url"]).status_code == 401
        assert public.json()["data"]["publication"]["tags"] == ["挂件", "审核测试"]
        finished_photo_url = public.json()["data"]["finished_photo_preview_url"]
        assert finished_photo_url
        assert client.get(finished_photo_url).status_code == 200
        assert client.get(finished_photo.json()["data"]["preview_url"]).status_code == 401
        gallery = client.get("/api/v1/publications?query=第一张")
        assert gallery.status_code == 200, gallery.text
        assert gallery.json()["data"]["total"] == 1
        assert gallery.json()["data"]["items"][0]["public_token"] == publication["public_token"]
        favorite = client.post(f"/api/v1/publications/{publication['public_token']}/favorite", headers=creator_headers)
        assert favorite.status_code == 200, favorite.text
        favorites = client.get("/api/v1/publications/favorites/mine", headers=creator_headers)
        assert [item["public_token"] for item in favorites.json()["data"]] == [publication["public_token"]]
        favorites_page = client.get(
            "/api/v1/publications/favorites/mine/page", params={"page_size": 1}, headers=creator_headers
        )
        assert favorites_page.status_code == 200, favorites_page.text
        assert favorites_page.json()["data"]["total"] == 1
        favorite_tokens = client.get("/api/v1/publications/favorites/mine/tokens", headers=creator_headers)
        assert favorite_tokens.json()["data"]["items"] == [publication["public_token"]]
        remix = client.post(f"/api/v1/publications/{publication['public_token']}/remix", headers=creator_headers)
        assert remix.status_code == 201, remix.text
        remix_data = remix.json()["data"]
        assert remix_data["pattern"]["id"] != blank.json()["data"]["id"]
        assert client.get(f"/api/v1/projects/{remix_data['project']['id']}", headers=creator_headers).status_code == 200
        withdrawn = client.delete(f"/api/v1/publications/{publication['id']}", headers=creator_headers)
        assert withdrawn.status_code == 204
        assert client.get(f"/api/v1/publications/{publication['public_token']}").status_code == 404
        assert client.get("/api/v1/publications?query=第一张").json()["data"]["total"] == 0
        owner_publications = client.get("/api/v1/publications/mine", headers=creator_headers).json()["data"]
        assert next(item for item in owner_publications if item["id"] == publication["id"])["status"] == "withdrawn"
        resubmitted = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/publications",
            json={"title": "管理员下架测试", "tags": ["管理测试"]},
            headers=creator_headers,
        )
        assert resubmitted.status_code == 201, resubmitted.text
        reviewed_again = client.post(
            f"/api/v1/admin/publications/{resubmitted.json()['data']['id']}/review",
            json={"decision": "approved", "checks": ["pattern_content", "metadata", "rights_privacy"]},
            headers=admin_headers,
        )
        assert reviewed_again.status_code == 200, reviewed_again.text
        missing_takedown_reason = client.delete(
            f"/api/v1/admin/publications/{resubmitted.json()['data']['id']}",
            headers=admin_headers,
        )
        assert missing_takedown_reason.status_code == 422
        taken_down = client.delete(
            f"/api/v1/admin/publications/{resubmitted.json()['data']['id']}",
            params={"note": "不符合当前社区展示规范"},
            headers=admin_headers,
        )
        assert taken_down.status_code == 204
        assert client.get(f"/api/v1/publications/{resubmitted.json()['data']['public_token']}").status_code == 404
        deleted_source_project = client.delete(
            f"/api/v1/projects/{project.json()['data']['id']}", headers=creator_headers
        )
        assert deleted_source_project.status_code == 204
        resumed = client.post(
            f"/api/v1/publications/{resubmitted.json()['data']['id']}/resume", headers=creator_headers
        )
        assert resumed.status_code == 200, resumed.text
        resumed_project = resumed.json()["data"]
        assert resumed_project["id"] != project.json()["data"]["id"]
        assert resumed_project["pattern_id"] == resubmitted.json()["data"]["pattern_id"]
        resumed_again = client.post(
            f"/api/v1/publications/{resubmitted.json()['data']['id']}/resume", headers=creator_headers
        )
        assert resumed_again.status_code == 200, resumed_again.text
        assert resumed_again.json()["data"]["id"] == resumed_project["id"]
        assert client.get(f"/api/v1/projects/{resumed_project['id']}", headers=creator_headers).status_code == 200
        owner_publications = client.get("/api/v1/publications/mine", headers=creator_headers).json()["data"]
        resubmitted_id = resubmitted.json()["data"]["id"]
        taken_down_owner_copy = next(item for item in owner_publications if item["id"] == resubmitted_id)
        assert taken_down_owner_copy["status"] == "withdrawn"
        assert taken_down_owner_copy["review_note"] == "不符合当前社区展示规范"
        admin_withdrawn = client.get("/api/v1/admin/publications?status=withdrawn", headers=admin_headers)
        assert admin_withdrawn.status_code == 200
        assert any(item["id"] == resubmitted.json()["data"]["id"] for item in admin_withdrawn.json()["data"])
        deleted_publication = client.delete(f"/api/v1/publications/{resubmitted_id}/record", headers=creator_headers)
        assert deleted_publication.status_code == 204
        remaining_publications = client.get("/api/v1/publications/mine", headers=creator_headers).json()["data"]
        assert all(item["id"] != resubmitted_id for item in remaining_publications)
        assert client.post(f"/api/v1/publications/{resubmitted_id}/resume", headers=creator_headers).status_code == 404

        users = client.get("/api/v1/admin/users", headers=admin_headers).json()["data"]["items"]
        creator = next(item for item in users if item["email"] == "creator@example.com")
        reset = client.put(
            f"/api/v1/admin/users/{creator['id']}/password",
            json={"password": "changed-password-456"},
            headers=admin_headers,
        )
        assert reset.status_code == 204
        assert client.get("/api/v1/auth/me", headers=creator_headers).status_code == 401
        renewed = client.post(
            "/api/v1/auth/login", json={"email": "creator@example.com", "password": "changed-password-456"}
        )
        assert renewed.status_code == 200, renewed.text
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_admin_review_blocks_empty_or_missing_pattern_but_still_allows_rejection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    monkeypatch.setenv("INITIAL_ADMIN_EMAILS", "review-admin@example.com")
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    with TestClient(create_app()) as client:
        admin_headers = _register(client, "review-admin@example.com")
        creator_headers = _register(client, "empty-pattern-owner@example.com")
        pattern = client.post(
            "/api/v1/patterns/blank",
            json={"grid_width": 4, "grid_height": 4},
            headers=creator_headers,
        )
        project = client.post(
            "/api/v1/projects",
            json={"name": "空图纸审核测试", "pattern_id": pattern.json()["data"]["id"]},
            headers=creator_headers,
        )
        submitted = client.post(
            f"/api/v1/projects/{project.json()['data']['id']}/publications",
            json={"title": "不可通过的空图纸"},
            headers=creator_headers,
        )
        publication_id = submitted.json()["data"]["id"]

        empty_detail = client.get(f"/api/v1/admin/publications/{publication_id}", headers=admin_headers)
        assert empty_detail.status_code == 200, empty_detail.text
        assert empty_detail.json()["data"]["review_readiness"]["can_approve"] is False
        assert "图纸中没有可见的拼豆单元格" in empty_detail.json()["data"]["review_readiness"]["blocking_issues"]
        blocked_approval = client.post(
            f"/api/v1/admin/publications/{publication_id}/review",
            json={"decision": "approved", "checks": ["pattern_content", "metadata", "rights_privacy"]},
            headers=admin_headers,
        )
        assert blocked_approval.status_code == 422
        assert blocked_approval.json()["code"] == "PUBLICATION_NOT_REVIEWABLE"

        deleted_pattern = client.delete(f"/api/v1/patterns/{pattern.json()['data']['id']}", headers=creator_headers)
        assert deleted_pattern.status_code == 204
        missing_detail = client.get(f"/api/v1/admin/publications/{publication_id}", headers=admin_headers)
        assert missing_detail.status_code == 200, missing_detail.text
        assert missing_detail.json()["data"]["pattern"] is None
        assert missing_detail.json()["data"]["review_readiness"]["can_approve"] is False
        rejected = client.post(
            f"/api/v1/admin/publications/{publication_id}/review",
            json={"decision": "rejected", "note": "图纸为空或资源已丢失，请修复后重新提交"},
            headers=admin_headers,
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["data"]["status"] == "rejected"
    get_settings.cache_clear()
    get_palette_service.cache_clear()


def test_users_can_update_profile_and_change_their_own_password(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "perler-studio.db"))
    get_settings.cache_clear()
    get_palette_service.cache_clear()
    with TestClient(create_app()) as client:
        headers = _register(client, "profile@example.com")
        updated = client.patch("/api/v1/auth/me", json={"display_name": "新的创作者名称"}, headers=headers)
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["display_name"] == "新的创作者名称"
        incorrect = client.put(
            "/api/v1/auth/me/password",
            json={"current_password": "wrong-password", "new_password": "new-password-789"},
            headers=headers,
        )
        assert incorrect.status_code == 401
        changed = client.put(
            "/api/v1/auth/me/password",
            json={"current_password": "secure-password-123", "new_password": "new-password-789"},
            headers=headers,
        )
        assert changed.status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        login = client.post("/api/v1/auth/login", json={"email": "profile@example.com", "password": "new-password-789"})
        assert login.status_code == 200, login.text
    get_settings.cache_clear()
    get_palette_service.cache_clear()
