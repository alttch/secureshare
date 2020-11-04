SELECT mimetype,
       oneshot,
       sha256sum,
       data
FROM stor
WHERE id=:id
  AND fname=:fname
  AND expires>:d
