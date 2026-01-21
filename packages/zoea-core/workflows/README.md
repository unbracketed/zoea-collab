For control flow: Pocketflow
For agents: [smolagent](https://huggingface.co/docs/smolagents/index)

Workflows can be defined throughout the platform by declaring a dotted path to the workflow package, module, or config file in a Django setting `INSTALLED_WORKFLOWS`

The Workflow Runner will load and register workflow definitions via:

1. A backend.workflows.types.Workflow 
2. A YAML config file named `flow-config.yaml`
 
Workflows should have a "slug" or name ID field that they can be referred to by.

## Inputs

A contract for data available to the workflow. Multiple inputs can be specified in a list. An Input is defined by: name, type, and value. Typically, values will not be specified at the configuration level for inputs; values will gathered at the start of the run from user input and the environment as needed.

The type for an Input will be a subset of Pydantic types, or special interal types presented by the Zoea platform for accessing project and workspace resources like documents or clipboards.

Examples of internal types: `Folder`, `MarkdownDocument`, `Clipboard`, `D2Diagram`


```yaml
INPUTS:
  - name: issue_number
    type: PositiveInt
  - name: feature_notes
    type: MarkdownDocument
  - name: mockups
    type: Folder
```

With `value` specified for the inputs:

```yaml
INPUTS:
  - name: issue_number
    type: PositiveInt
    value: 7
  - name: feature_notes
    type: MarkdownDocument
    value: Planning/Features/Issue Triage/planning-doc.md
  - name: mockups
    type: Folder
    value: Planning/Features/Issue Triage/Mockup Designs
```


### Typed Value Inputs 

Collect via request parameter in query string, present a form, user input in CLI. 

Example of inputs can being passed via request param:
`http://local.zoea.studio:20000/workflows/gh-impl-spec?issue_number=7`


### Folder (Documents collection)

Value types: Folder path or ID

```yaml
INPUTS:
  - name: source_images
    type: Folder
    value: Design/Brand Research
```

### Clipboard (Documents collection)

Value types: clipboard name or ID

```yaml
INPUTS:
  - name: source_images
    type: Clipboard
```


## Outputs

A contract for data the workflow produces. A workflow can produce multiple outputs, specified in a list.

Output has:

- name
- type
- target

Can reference input values via bracketed variables similar to Python format strings. Here is an 
example where `issue_number` is assumed to be an Input parameter with a value that was specified or collected earlier.


```yaml
OUTPUTS:
  - name: Issue {issue_number} Implementation Spec
    type: MarkdownDocument
    target: SDLC/Specs/Issue-{issue_number}
```


## Plugins / Services

This is the tools / MCP layer. Plugins provide access to external data and services in a standardized way. 

Plugin has:

- name: name of the plugin / service to use
- ctxref: identifier variable for service in workflow code

```yaml
SERVICES:
  - name: PyGithubInterface
    ctxref: gh
```

Example referencing the service:

```python
def prep(self, ctx):
    return ctx.services.gh.read_issue(ctx.inputs.issue_number)
```

Use Pluggy?

Some likely plugins we'll want to develop or include: Github, Harvest, Nanobanana, Unstructured, File Search? 

## Runner

read worker definition, metadata, introspect inputs, outputs
collect inputs via generated forms or inputs
collects outputs from state / end node

---

Let's try to get to a working implementation for the builtin workflow plan_github_issue. The `workflows` dir is currently more a collection of notes and ideas right. Help me fill in missing details in the spec
  @backend/workflows/README.md I want to build a workflow runner that will run workflows which can be defined via a mix of Python code and configuration files. We are working toward supporting a workflow view(s)
  in the app, but the CLI is also a good way to interact. For example `zoea workflow plan-github-issue --issue_number=7`
  https://github.com/The-Pocket/PocketFlow/blob/main/docs/guide.md