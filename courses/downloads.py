"""Authenticated downloads, including byte ranges for lesson video playback."""
import mimetypes
import re
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils.cache import patch_cache_control
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_safe

from .access import resolve_course_access
from .models import CourseMaterial, Lesson, LessonMaterial


def _stream_range(file, start, length):
    try:
        file.seek(start)
        while length > 0:
            chunk = file.read(min(64 * 1024, length))
            if not chunk:
                break
            length -= len(chunk)
            yield chunk
    finally:
        file.close()


def _file_response(request, field, video=False):
    try:
        file = field.open("rb")
        size = field.size
    except (FileNotFoundError, OSError):
        raise Http404("Файл не найден")
    filename = Path(field.name).name
    # Arbitrary documents are downloaded, never executed as same-origin HTML.
    content_type = (mimetypes.guess_type(filename)[0] or "application/octet-stream") if video else "application/octet-stream"
    headers = {
        "Content-Disposition": content_disposition_header(not video, filename),
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Vary": "Cookie",
    }
    range_header = request.headers.get("Range") if request.method == "GET" else None
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        try:
            if not match or not any(match.groups()) or size == 0:
                raise ValueError
            first, last = match.groups()
            start = int(first) if first else max(0, size - int(last))
            end = min(int(last), size - 1) if first and last else size - 1
            if start >= size or start > end:
                raise ValueError
        except ValueError:
            file.close()
            return HttpResponse(status=416, headers={**headers, "Content-Range": f"bytes */{size}"})
        length = end - start + 1
        headers.update({"Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(length)})
        response = StreamingHttpResponse(_stream_range(file, start, length), status=206, content_type=content_type, headers=headers)
        response._resource_closers.append(file.close)
        return response
    if request.method == "HEAD":
        file.close()
        return HttpResponse(content_type=content_type, headers={**headers, "Content-Length": str(size)})
    return FileResponse(file, as_attachment=not video, filename=filename, content_type=content_type, headers=headers)


@login_required
@require_safe
def private_file(request, name):
    material = CourseMaterial.objects.select_related("course").filter(file=name).first()
    video = False
    if material:
        course, published, field = material.course, material.is_published, material.file
    else:
        material = LessonMaterial.objects.select_related("lesson__course").filter(file=name).first()
        if material:
            course = material.lesson.course
            published = material.is_published and material.lesson.is_published
            field = material.file
        else:
            material = Lesson.objects.select_related("course").filter(video_file=name).first()
            if not material:
                raise Http404
            course, published, field = material.course, material.is_published, material.video_file
            video = True

    opts = material._meta
    can_manage = request.user.is_active and request.user.is_staff and (
        request.user.has_perm(f"{opts.app_label}.view_{opts.model_name}")
        or request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")
    )
    if not can_manage and (not published or not resolve_course_access(request.user, course.slug).allowed):
        raise Http404
    response = _file_response(request, field, video=video)
    patch_cache_control(response, private=True, no_store=True)
    return response
