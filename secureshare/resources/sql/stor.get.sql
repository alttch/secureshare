SELECT mimetype,
       oneshot,
       DATA
FROM stor
WHERE id=:id
  AND fname=:fname
