/* Crop-on-upload for doctor photos.
   Choose a photo -> a crop window opens (4:3, same frame as the website cards) -> the cropped image
   replaces the chosen file, so the normal form submit uploads the cropped version.
   Uses Cropper.js from a CDN; if it cannot load, the original file is uploaded unchanged. */
(function () {
  var ASPECT = 4 / 3, OUT_W = 800, OUT_H = 600;
  var CSS = "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.css";
  var JS = "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.2/cropper.min.js";
  var loading = null;

  function load() {
    if (window.Cropper) return Promise.resolve();
    if (loading) return loading;
    var l = document.createElement("link"); l.rel = "stylesheet"; l.href = CSS; document.head.appendChild(l);
    loading = new Promise(function (ok, fail) {
      var s = document.createElement("script"); s.src = JS; s.onload = ok; s.onerror = fail; document.head.appendChild(s);
    });
    return loading;
  }

  var style = document.createElement("style");
  style.textContent =
    ".crop-ov{position:fixed;inset:0;background:rgba(20,5,9,.72);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px}" +
    ".crop-box{background:#fff;border-radius:16px;width:min(680px,100%);max-height:96vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.35)}" +
    ".crop-box h3{margin:0;padding:16px 20px 4px;font-size:18px}" +
    ".crop-box p{margin:0;padding:0 20px 12px;color:#6b5b5f;font-size:13px}" +
    ".crop-stage{height:min(60vh,440px);background:#1d1417}.crop-stage img{display:block;max-width:100%}" +
    ".crop-bar{display:flex;flex-wrap:wrap;gap:8px;padding:14px 20px;align-items:center;border-top:1px solid #f0e3e5}" +
    ".crop-bar .sp{flex:1}" +
    ".crop-bar button{border:1px solid #e3c9cd;background:#fff;color:#7d0c1e;border-radius:999px;padding:8px 14px;font:inherit;font-weight:600;font-size:14px;cursor:pointer}" +
    ".crop-bar button.main{background:#b3122b;border-color:#b3122b;color:#fff}" +
    ".crop-bar button:hover{filter:brightness(.95)}";
  document.head.appendChild(style);

  function openCropper(input, file) {
    var url = URL.createObjectURL(file), cropper = null;
    var ov = document.createElement("div"); ov.className = "crop-ov";
    ov.innerHTML =
      '<div class="crop-box" role="dialog" aria-modal="true" aria-label="Crop photo">' +
      '<h3>Crop doctor photo</h3><p>Drag to move, scroll or use the buttons to zoom. This is exactly how it will appear on the website.</p>' +
      '<div class="crop-stage"><img alt=""></div>' +
      '<div class="crop-bar">' +
      '<button type="button" data-a="in">Zoom +</button><button type="button" data-a="out">Zoom &minus;</button>' +
      '<button type="button" data-a="rot">Rotate</button><button type="button" data-a="reset">Reset</button><span class="sp"></span>' +
      '<button type="button" data-a="cancel">Cancel</button><button type="button" data-a="orig">Use original</button>' +
      '<button type="button" class="main" data-a="ok">Use cropped photo</button></div></div>';
    document.body.appendChild(ov);
    var img = ov.querySelector("img"); img.src = url;

    function close() { if (cropper) cropper.destroy(); URL.revokeObjectURL(url); ov.remove(); }
    function setFile(f) {
      var dt = new DataTransfer(); dt.items.add(f); input.files = dt.files;
      input.dataset.cropped = "1"; input.dispatchEvent(new Event("change", { bubbles: true })); delete input.dataset.cropped;
    }

    load().then(function () {
      cropper = new Cropper(img, { aspectRatio: ASPECT, viewMode: 1, dragMode: "move", autoCropArea: 1, background: false, guides: true, responsive: true });
    }).catch(function () { close(); });  // CDN blocked: keep the original file

    ov.addEventListener("click", function (e) {
      var a = e.target.getAttribute && e.target.getAttribute("data-a");
      if (!a || !cropper) { if (a === "cancel") { input.value = ""; close(); } return; }
      if (a === "in") cropper.zoom(0.1);
      else if (a === "out") cropper.zoom(-0.1);
      else if (a === "rot") cropper.rotate(90);
      else if (a === "reset") cropper.reset();
      else if (a === "cancel") { input.value = ""; close(); }
      else if (a === "orig") close();
      else if (a === "ok") {
        var canvas = cropper.getCroppedCanvas({ width: OUT_W, height: OUT_H, fillColor: "#fff", imageSmoothingQuality: "high" });
        canvas.toBlob(function (blob) {
          var base = (file.name || "photo").replace(/\.[^.]+$/, "");
          setFile(new File([blob], base + "-cropped.jpg", { type: "image/jpeg" }));
          close();
        }, "image/jpeg", 0.92);
      }
    });
  }

  document.querySelectorAll('input[type=file][name=photo]').forEach(function (input) {
    input.addEventListener("change", function (e) {
      if (input.dataset.cropped) return;  // the change we fired ourselves after cropping
      var f = input.files && input.files[0];
      if (!f || f.type.indexOf("image/") !== 0 || !window.DataTransfer) return;
      e.stopImmediatePropagation();  // hold the preview until the crop is done
      openCropper(input, f);
    });
  });
})();
