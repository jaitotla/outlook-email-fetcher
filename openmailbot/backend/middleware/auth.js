/**
 * Authentication middleware
 */

exports.isAuthenticated = (req, res, next) => {
  if (req.isAuthenticated()) {
    return next();
  }
  res.status(401).json({ error: 'Unauthorized' });
};

exports.isAdmin = (req, res, next) => {
  if (req.isAuthenticated() && req.user.role === 'admin') {
    return next();
  }
  res.status(403).json({ error: 'Forbidden: Admin access required' });
};

exports.isManagerOrAdmin = (req, res, next) => {
  if (req.isAuthenticated() && ['admin', 'manager'].includes(req.user.role)) {
    return next();
  }
  res.status(403).json({ error: 'Forbidden: Manager or Admin access required' });
};
