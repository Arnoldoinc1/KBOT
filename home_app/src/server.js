const path = require("path");
const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
require("dotenv").config();

const app = express();

const port = Number(process.env.PORT || 3000);

function makeProxy(target, label) {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    pathRewrite: (proxyPath) => proxyPath.replace(new RegExp(`^/${label}`), "") || "/",
    on: {
      proxyReq: (proxyReq, req) => {
        proxyReq.setHeader("X-Forwarded-Prefix", `/${label}`);
        // http-proxy-middleware pipes the original request body straight through
        // (no body-parser middleware consumes it here), so nothing to re-send.
      },
      error: (err, req, res) => {
        console.error(`Proxy error for ${label}:`, err.message);
        if (!res.headersSent) {
          res.status(502).send("Sub application is unavailable.");
        }
      }
    }
  });
}

// Redirect the old /quiz path to the student site, and normalize top-level
// prefixes (plus the nested /teacher/solver) to a trailing slash. The solver
// page uses relative asset paths (assets/style.css), which only resolve
// correctly when the document URL ends in "/" — /teacher/solver without a
// slash would resolve them to /teacher/assets/* and 404 on the teacher app.
// strict-routing:false makes /teacher also match /teacher/, so avoid
// double-slash redirects by checking req.path.
app.get(["/quiz", "/student", "/teacher", "/solver", "/teacher/solver"], (req, res, next) => {
  if (req.path === "/quiz") return res.redirect("/student/");
  if (req.path.endsWith("/")) return next("route");
  res.redirect(`${req.path}/`);
});

app.get("/health", (req, res) => {
  res.json({ ok: true, app: "home-app" });
});

// Proxy order matters: the nested /teacher/solver route must be registered
// before the broader /teacher route so the math solver is hit first.
app.use("/teacher/solver", makeProxy(process.env.SOLVER_TARGET || "http://solver-app:5000", "teacher/solver"));
app.use("/teacher", makeProxy(process.env.TEACHER_TARGET || "http://teacher-app:5000", "teacher"));
app.use("/student", makeProxy(process.env.STUDENT_TARGET || "http://student-app:8000", "student"));
app.use("/solver", makeProxy(process.env.SOLVER_TARGET || "http://solver-app:5000", "solver"));

// Landing page with the Student / Teacher cards.
app.use(express.static(path.join(__dirname, "public")));

app.listen(port, () => {
  console.log(`Home app listening on port ${port}`);
});
