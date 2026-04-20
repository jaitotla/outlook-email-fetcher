const mongoose = require('mongoose');
const { v4: uuidv4 } = require('uuid');

const groupSchema = new mongoose.Schema({
  id: {
    type: String,
    default: uuidv4,
    unique: true
  },
  tenantId: {
    type: String,
    ref: 'Tenant',
    required: true,
    index: true
  },
  name: {
    type: String,
    required: true
  },
  managerId: {
    type: String,
    ref: 'User'
  },
  members: [{
    type: String,
    ref: 'User'
  }],
  active: {
    type: Boolean,
    default: true
  }
}, {
  timestamps: true
});

groupSchema.index({ tenantId: 1, name: 1 });

module.exports = mongoose.model('Group', groupSchema);
