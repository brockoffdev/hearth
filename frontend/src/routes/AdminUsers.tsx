import { useEffect, useState } from 'react';
import type { JSX, FormEvent } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { HBtn } from '../components/HBtn';
import { Spinner } from '../components/Spinner';
import {
  listUsers,
  createUser,
  patchUser,
  deleteUser,
} from '../lib/adminUsers';
import type { AdminUser } from '../lib/adminUsers';
import { ApiError } from '../lib/api';
import styles from './AdminUsers.module.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ---------------------------------------------------------------------------
// Add-user modal
// ---------------------------------------------------------------------------

interface AddUserModalProps {
  onClose: () => void;
  onCreated: (user: AdminUser) => void;
}

function AddUserModal({ onClose, onCreated }: AddUserModalProps): JSX.Element {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'admin' | 'user'>('user');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await createUser({ username, password, role });
      onCreated(user);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Username already taken');
      } else if (err instanceof ApiError && err.status === 422) {
        setError(err.message);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Add user">
      <div className={styles.modal}>
        <h2 className={styles.modalTitle}>Add user</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className={styles.fieldGroup}>
          <div className={styles.field}>
            <label htmlFor="new-username" className={styles.fieldLabel}>
              Username
            </label>
            <input
              id="new-username"
              type="text"
              className={styles.fieldInput}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="off"
              autoFocus
              required
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="new-password" className={styles.fieldLabel}>
              Password
            </label>
            <input
              id="new-password"
              type="password"
              className={styles.fieldInput}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="new-role" className={styles.fieldLabel}>
              Role
            </label>
            <select
              id="new-role"
              className={styles.fieldSelect}
              value={role}
              onChange={(e) => setRole(e.target.value as 'admin' | 'user')}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          {error !== null && (
            <p className={styles.inlineError} role="alert">
              {error}
            </p>
          )}
          <div className={styles.modalActions}>
            <HBtn kind="ghost" type="button" onClick={onClose} disabled={submitting}>
              Cancel
            </HBtn>
            <HBtn kind="primary" type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create user'}
            </HBtn>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// User row
// ---------------------------------------------------------------------------

interface UserRowProps {
  user: AdminUser;
  isSelf: boolean;
  onRoleToggled: (updated: AdminUser) => void;
  onDeleted: (id: number) => void;
}

function UserRow({ user, isSelf, onRoleToggled, onDeleted }: UserRowProps): JSX.Element {
  const [showPwForm, setShowPwForm] = useState(false);
  const [newPw, setNewPw] = useState('');
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwSubmitting, setPwSubmitting] = useState(false);

  async function handleToggleRole(): Promise<void> {
    const nextRole = user.role === 'admin' ? 'user' : 'admin';
    const updated = await patchUser(user.id, { role: nextRole });
    onRoleToggled(updated);
  }

  async function handlePwSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setPwSubmitting(true);
    await patchUser(user.id, { new_password: newPw });
    setPwSuccess(true);
    setNewPw('');
    setPwSubmitting(false);
    setTimeout(() => {
      setShowPwForm(false);
      setPwSuccess(false);
    }, 1500);
  }

  async function handleDelete(): Promise<void> {
    if (window.confirm(`Delete user ${user.username}? This cannot be undone.`)) {
      await deleteUser(user.id);
      onDeleted(user.id);
    }
  }

  return (
    <div className={styles.tableRow}>
      <div>
        <span className={isSelf ? styles.usernameSelf : styles.username}>
          {user.username}
        </span>
        {isSelf && <span className={styles.selfBadge}>you</span>}
      </div>
      <div>
        <span className={user.role === 'admin' ? styles.rolePillAdmin : styles.rolePillUser}>
          {user.role === 'admin' ? 'Admin' : 'User'}
        </span>
      </div>
      <div>
        <span className={styles.dateText}>{formatDate(user.created_at)}</span>
      </div>
      <div className={styles.actions}>
        {showPwForm ? (
          <form onSubmit={(e) => void handlePwSubmit(e)} className={styles.pwForm}>
            {pwSuccess ? (
              <span className={styles.pwSuccess} role="status">
                Password updated
              </span>
            ) : (
              <>
                <input
                  type="password"
                  className={styles.pwInput}
                  placeholder="New password"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  autoFocus
                  required
                  aria-label="New password"
                />
                <HBtn kind="primary" type="submit" size="sm" disabled={pwSubmitting}>
                  Save
                </HBtn>
                <HBtn
                  kind="ghost"
                  type="button"
                  size="sm"
                  onClick={() => setShowPwForm(false)}
                >
                  Cancel
                </HBtn>
              </>
            )}
          </form>
        ) : (
          <>
            <HBtn
              kind="ghost"
              size="sm"
              onClick={() => setShowPwForm(true)}
              aria-label={`Reset password for ${user.username}`}
            >
              Reset pwd
            </HBtn>
            <HBtn
              kind="ghost"
              size="sm"
              disabled={isSelf}
              onClick={() => void handleToggleRole()}
              aria-label={`Toggle role for ${user.username}`}
            >
              {user.role === 'admin' ? 'Make user' : 'Make admin'}
            </HBtn>
            <HBtn
              kind="danger"
              size="sm"
              disabled={isSelf}
              onClick={() => void handleDelete()}
              aria-label={`Delete ${user.username}`}
            >
              Delete
            </HBtn>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 403 view
// ---------------------------------------------------------------------------

function ForbiddenView(): JSX.Element {
  return (
    <div className={styles.forbidden}>
      <div className={styles.forbiddenCard}>
        <h1 className={styles.forbiddenTitle}>403</h1>
        <p className={styles.forbiddenText}>Admin access required.</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdminUsers(): JSX.Element {
  const { state } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  const isAdmin = state.status === 'authenticated' && state.user.role === 'admin';
  const currentUserId =
    state.status === 'authenticated' ? state.user.id : null;

  useEffect(() => {
    if (!isAdmin) return;
    listUsers()
      .then(setUsers)
      .catch(() => {/* auth redirect handled by RequireAuth */})
      .finally(() => setLoading(false));
  }, [isAdmin]);

  if (state.status === 'loading') {
    return (
      <div className={styles.page} role="status" aria-live="polite">
        <Spinner size={20} />
      </div>
    );
  }

  if (state.status !== 'authenticated' || state.user.role !== 'admin') {
    return <ForbiddenView />;
  }

  function handleCreated(user: AdminUser): void {
    setUsers((prev) => [user, ...prev]);
    setShowModal(false);
  }

  function handleRoleToggled(updated: AdminUser): void {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
  }

  function handleDeleted(id: number): void {
    setUsers((prev) => prev.filter((u) => u.id !== id));
  }

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={styles.content}>
          <div className={styles.heading}>
            <div className={styles.adminLabel}>Admin</div>
            <h1 className={styles.title}>
              <span className={styles.titleAccent}>Users</span>
            </h1>
            <p className={styles.subtitle}>Add and remove people who can use Hearth.</p>
          </div>

          <div className={styles.tableCard}>
            <div className={styles.tableHeader}>
              <span>Username</span>
              <span>Role</span>
              <span>Created</span>
              <span>Actions</span>
            </div>
            {loading ? (
              <div className={styles.tableRow}>
                <span style={{ color: 'var(--fgSoft)', fontSize: 13 }}>Loading…</span>
              </div>
            ) : users.length === 0 ? (
              <div className={styles.tableRow}>
                <span style={{ color: 'var(--fgSoft)', fontSize: 13 }}>No users yet.</span>
              </div>
            ) : (
              users.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  isSelf={user.id === currentUserId}
                  onRoleToggled={handleRoleToggled}
                  onDeleted={handleDeleted}
                />
              ))
            )}
          </div>

          <div className={styles.footer}>
            <HBtn kind="primary" onClick={() => setShowModal(true)}>
              + Add user
            </HBtn>
          </div>
        </div>
      </div>

      {showModal && (
        <AddUserModal
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
