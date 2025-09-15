# color-logs.jq (256-color)
# Usage: ... 2>&1 | jq -Rr -f ~/.jq/color-logs.jq | less -R

def NC: (env.NO_COLOR // "") != "";
def esc: if NC then "" else "\u001b[" end;
def R: if NC then "" else esc + "0m" end;
def B: if NC then "" else esc + "1m" end;
def F(c): if NC then "" else esc + "38;5;" + (c|tostring) + "m" end;

# palette (tweak to taste)
def COL_TS:    245;  # dim gray
def COL_LOG:    69;  # blue-ish
def COL_INFO:   76;  # green
def COL_WARN:  178;  # amber
def COL_ERROR: 196;  # red
def COL_DEBUG:  39;  # cyan

def ts(s): (if (s|type)=="string" and (s|length)>=19 then s[11:19] else "--:--:--" end) as $t
           | (F(COL_TS) + $t + R);

def lvlc(s):
  (s|tostring|ascii_upcase) as $l
  | if   $l=="INFO"  then F(COL_INFO)+"INFO "+R
    elif ($l=="WARN" or $l=="WARNING") then F(COL_WARN)+"WARN "+R
    elif $l=="ERROR" then F(COL_ERROR)+"ERROR"+R
    elif $l=="DEBUG" then F(COL_DEBUG)+"DEBUG"+R
    else B + $l + R end;

def logc(s): F(COL_LOG) + (s|tostring) + R;

. as $line
| (if $line|test("^\\s*\\{") then ($line|try fromjson catch $line) else $line end) as $x
| if ($x|type)=="object" then
    "\(ts($x.timestamp))  \(lvlc($x.level))  \(logc(($x.logger|tostring|split(".")|last))) - \($x.message // $x.request // "")"
  else
    if $line|test("^[A-Z]+:\\s") then
      ($line|capture("^(?<lvl>[A-Z]+):\\s*(?<rest>.*)")) as $m
      | "\(F(COL_TS))--:--:--\(R)  \(lvlc($m.lvl))  \(logc("uvicorn")) - \($m.rest)"
    else
      $line
    end
  end
